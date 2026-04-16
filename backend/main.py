"""
AI Research Assistant - FastAPI Backend
Phases: Paper Discovery → Summarize → PDF Upload → RAG → Knowledge Graph
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import httpx
import os
import re
import collections
import json
import tempfile
import asyncio
import time
from datetime import datetime, timedelta
from groq import Groq
import fitz  # PyMuPDF
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
import logging

from dotenv import load_dotenv

# Import KG modules
from neo4j_kg import KnowledgeGraphManager, init_knowledge_graph_manager, get_kg_manager
from kg_builder import KnowledgeGraphBuilder

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# ─── App Setup ────────────────────────────────────────────────────────────────
app = FastAPI(title="AI Research Assistant", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Config ───────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SEMANTIC_SCHOLAR_BASE = "https://api.semanticscholar.org/graph/v1"

groq_client = Groq(api_key=GROQ_API_KEY)

# ─── RAG State (in-memory for prototype) ─────────────────────────────────────
rag_index = None
rag_chunks = []
rag_metadata = []
embedding_model = None

# ─── Knowledge Graph State ───────────────────────────────────────────────────
kg_manager = None
kg_builder = None
current_paper_id = None  # Track current paper for KG queries

# ─── Search Cache (restored from v1) ─────────────────────────────────────────
SEARCH_CACHE = {}


def get_embedding_model():
    global embedding_model
    if embedding_model is None:
        logger.info("Loading embedding model...")
        embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return embedding_model


# ─── Startup / Shutdown ───────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    global kg_manager, kg_builder
    logger.info("🚀 Starting up AI Research Assistant...")

    kg_manager = init_knowledge_graph_manager()
    kg_builder = KnowledgeGraphBuilder(groq_client)

    if kg_manager and kg_manager.is_connected():
        logger.info("✓ Knowledge graph system initialized")
    else:
        logger.warning("⚠ Knowledge graph system disabled (Neo4j not available)")
        logger.info("  To enable: set NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD in .env")


@app.on_event("shutdown")
async def shutdown_event():
    global kg_manager
    if kg_manager:
        kg_manager.close()
        logger.info("Knowledge graph connection closed")


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1 — PAPER DISCOVERY
# ═══════════════════════════════════════════════════════════════════════════════

_last_request_time: float = 0.0
_MIN_REQUEST_INTERVAL = 1.2   # seconds between requests to Semantic Scholar


async def _fetch_with_retry(url: str, params: dict, max_retries: int = 3) -> dict:
    """
    Call Semantic Scholar with:
      • Minimum 1.2 s gap between requests
      • Exponential back-off on 429 (2 s → 4 s → 8 s)
      • Automatic fallback: remove date filter on 4xx
    """
    global _last_request_time

    elapsed = time.monotonic() - _last_request_time
    if elapsed < _MIN_REQUEST_INTERVAL:
        await asyncio.sleep(_MIN_REQUEST_INTERVAL - elapsed)

    headers = {"User-Agent": "AI-Research-Assistant/1.0 (learning project)"}

    last_err = None
    for attempt in range(max_retries):
        try:
            _last_request_time = time.monotonic()
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(url, params=params, headers=headers)

            if resp.status_code == 429:
                wait = 2 ** (attempt + 1)
                logger.warning(f"[papers] 429 rate-limit — waiting {wait}s (attempt {attempt + 1})")
                await asyncio.sleep(wait)
                last_err = f"Rate limited (429) — retried {attempt + 1} times"
                continue

            resp.raise_for_status()
            data = resp.json()
            if data.get("data"):
                return data
            break  # empty result with date filter → fall through to no-date fallback

        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Semantic Scholar API timed out")
        except httpx.HTTPStatusError as e:
            last_err = str(e)
            if e.response.status_code == 429:
                wait = 2 ** (attempt + 1)
                await asyncio.sleep(wait)
                continue
            break  # other 4xx → skip to fallback

    # ── Fallback: drop date + sort filters ───────────────────────────────────
    fallback_params = {k: v for k, v in params.items()
                       if k not in ("publicationDateOrYear", "sort")}
    logger.info("[papers] Trying fallback without date filter...")

    for attempt in range(max_retries):
        try:
            elapsed = time.monotonic() - _last_request_time
            if elapsed < _MIN_REQUEST_INTERVAL:
                await asyncio.sleep(_MIN_REQUEST_INTERVAL - elapsed)

            _last_request_time = time.monotonic()
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(url, params=fallback_params, headers=headers)

            if resp.status_code == 429:
                wait = 2 ** (attempt + 1)
                logger.warning(f"[papers] fallback 429 — waiting {wait}s")
                await asyncio.sleep(wait)
                continue

            resp.raise_for_status()
            return resp.json()

        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Semantic Scholar API timed out")
        except httpx.HTTPStatusError as e:
            last_err = str(e)
            if e.response.status_code == 429:
                wait = 2 ** (attempt + 1)
                await asyncio.sleep(wait)
                continue
            raise HTTPException(status_code=502, detail=f"Semantic Scholar error: {last_err}")

    raise HTTPException(
        status_code=429,
        detail="Semantic Scholar is rate-limiting us. Please wait 30 seconds and try again.",
    )


# ── OpenAlex fallback (restored from v1) ─────────────────────────────────────

async def _fetch_openalex(q: str, limit: int) -> dict:
    """Fallback paper search via OpenAlex when Semantic Scholar is unavailable."""
    try:
        url = "https://api.openalex.org/works"
        params = {"search": q, "per_page": limit}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)

        resp.raise_for_status()
        data = resp.json()

        papers = []
        for item in data.get("results", []):
            # Reconstruct abstract from inverted index (best-effort, not perfect ordering)
            abstract_index = item.get("abstract_inverted_index") or {}
            if abstract_index:
                # Rebuild ordered text from position→word mapping
                word_positions = []
                for word, positions in abstract_index.items():
                    for pos in positions:
                        word_positions.append((pos, word))
                word_positions.sort(key=lambda x: x[0])
                abstract = " ".join(w for _, w in word_positions)[:800]
            else:
                abstract = "No abstract available."

            papers.append({
                "paperId": item.get("id", ""),
                "title": item.get("title", ""),
                "abstract": abstract,
                "authors": [
                    a["author"]["display_name"]
                    for a in item.get("authorships", [])[:5]
                    if a.get("author", {}).get("display_name")
                ],
                "year": item.get("publication_year"),
                "publicationDate": item.get("publication_date"),
                "url": item.get("id"),
                "pdfUrl": item.get("open_access", {}).get("oa_url"),
            })

        return {"data": papers}

    except Exception as e:
        logger.warning(f"OpenAlex fallback failed: {e}")
        return {"data": []}


@app.get("/papers")
async def get_papers(q: str, limit: int = 10):
    """Fetch papers from Semantic Scholar (with OpenAlex fallback and cache)."""
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    cache_key = q.lower().strip()
    if cache_key in SEARCH_CACHE:
        logger.info("✅ Cache hit for query: %s", q)
        return SEARCH_CACHE[cache_key]

    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")

    url = f"{SEMANTIC_SCHOLAR_BASE}/paper/search"
    params = {
        "query": q,
        "limit": min(limit, 10),
        "fields": "title,abstract,authors,year,externalIds,openAccessPdf,url,publicationDate",
        "publicationDateOrYear": f"{seven_days_ago}:{today}",
        "sort": "publicationDate:desc",
    }

    # Try Semantic Scholar first
    try:
        data = await _fetch_with_retry(url, params)
    except HTTPException:
        data = None

    # Fallback to OpenAlex if Semantic Scholar failed or returned nothing
    if not data or not data.get("data"):
        logger.info("🔁 Switching to OpenAlex fallback...")
        data = await _fetch_openalex(q, limit)

    papers = []
    for paper in data.get("data", []):
        pdf_url = None

        # Semantic Scholar provides openAccessPdf
        if paper.get("openAccessPdf"):
            pdf_url = paper["openAccessPdf"].get("url")

        # Try arXiv ID as another PDF source
        ext_ids = paper.get("externalIds") or {}
        arxiv_id = ext_ids.get("ArXiv")
        if not pdf_url and arxiv_id:
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

        # Also accept pdfUrl directly (OpenAlex shape)
        if not pdf_url:
            pdf_url = paper.get("pdfUrl")

        # Build canonical paper URL
        paper_url = paper.get("url") or ""
        if not paper_url and arxiv_id:
            paper_url = f"https://arxiv.org/abs/{arxiv_id}"

        # Normalize authors — handle both {name: str} dicts and plain strings
        raw_authors = paper.get("authors") or []
        author_names = []
        for a in raw_authors[:5]:
            if isinstance(a, dict):
                name = a.get("name") or a.get("display_name") or ""
            else:
                name = str(a)
            if name:
                author_names.append(name)

        papers.append({
            "paperId": paper.get("paperId", ""),
            "title": paper.get("title") or "Untitled",
            "abstract": (paper.get("abstract") or "No abstract available.")[:800],
            "authors": author_names,
            "year": paper.get("year"),
            "publicationDate": paper.get("publicationDate"),
            "url": paper_url,
            "pdfUrl": pdf_url,
        })

    result = {"papers": papers, "total": len(papers), "query": q}
    SEARCH_CACHE[cache_key] = result
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — AI SUMMARIZATION (Groq)
# ═══════════════════════════════════════════════════════════════════════════════

class SummarizeRequest(BaseModel):
    text: str
    title: Optional[str] = None


@app.post("/summarize")
async def summarize(req: SummarizeRequest):
    """Summarize research text using Groq LLM."""
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    max_chars = 6000
    if len(text) > max_chars:
        text = text[:max_chars] + "...[truncated]"

    title_context = f'Title: "{req.title}"\n\n' if req.title else ""

    prompt = f"""You are an expert AI research assistant. Analyze this research paper and respond ONLY with valid JSON.

{title_context}Abstract/Text:
{text}

Respond with this exact JSON structure:
{{
  "summary": "2-3 sentence plain English explanation of what this paper does and why it matters",
  "key_points": ["point 1", "point 2", "point 3", "point 4"],
  "difficulty": "Beginner | Intermediate | Advanced",
  "research_area": "e.g. Computer Vision, NLP, Reinforcement Learning",
  "novelty": "What's new or different about this work in 1 sentence"
}}"""

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=700,
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"```json\s*", "", raw)
        raw = re.sub(r"```\s*", "", raw)
        return json.loads(raw)

    except json.JSONDecodeError:
        return {
            "summary": raw[:300] if raw else "Could not generate summary.",
            "key_points": ["See raw summary above"],
            "difficulty": "Unknown",
            "research_area": "Unknown",
            "novelty": "N/A",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Groq API error: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3 — PDF UPLOAD & EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    """Extract text from uploaded PDF, build RAG index, and optionally build Knowledge Graph."""
    global current_paper_id

    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    contents = await file.read()

    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        doc = fitz.open(tmp_path)
        full_text = [doc[page_num].get_text() for page_num in range(len(doc))]
        doc.close()
        os.unlink(tmp_path)

        raw_text = "\n".join(full_text)
        cleaned = _clean_pdf_text(raw_text)

        paper_id = file.filename.replace(".pdf", "").replace(" ", "_").lower()
        current_paper_id = paper_id

        # Build RAG index
        _build_rag_index(cleaned, file.filename)

        # Section-aware KG building
        section_texts = _extract_sections_from_text(raw_text)
        all_entities = []
        all_relationships = []
        section_info = []
        kg_success = False
        kg_stats = {"entities": 0, "relationships": 0, "sections": 0}

        if kg_manager and kg_manager.is_connected() and kg_builder:
            try:
                logger.info(f"Building section-aware knowledge graph for {paper_id}...")

                for section_name, section_text in section_texts.items():
                    entities, relationships = kg_builder.build_knowledge_graph(
                        section_text, paper_id, title=f"{file.filename} - {section_name}"
                    )
                    for e in entities:
                        e["section"] = section_name
                    for r in relationships:
                        r["section"] = section_name
                    all_entities.extend(entities)
                    all_relationships.extend(relationships)
                    section_info.append({
                        "section": section_name,
                        "entities": len(entities),
                        "relationships": len(relationships),
                    })

                # Fallback: whole text if no sections yielded results
                if not all_entities and not all_relationships:
                    entities, relationships = kg_builder.build_knowledge_graph(
                        cleaned, paper_id, title=file.filename
                    )
                    all_entities = entities
                    all_relationships = relationships
                    section_info.append({
                        "section": "ALL",
                        "entities": len(entities),
                        "relationships": len(relationships),
                    })

                if all_entities and all_relationships:
                    kg_success = kg_manager.create_paper_graph(
                        paper_id, file.filename, all_entities, all_relationships
                    )
                    kg_stats = {
                        "entities": len(all_entities),
                        "relationships": len(all_relationships),
                        "sections": len(section_info),
                    }
                    logger.info(f"Knowledge graph created: {kg_stats}")

            except Exception as e:
                logger.warning(f"Knowledge graph creation failed: {e}")
                kg_success = False

        kg_enabled = kg_manager is not None and kg_manager.is_connected()

        return {
            "filename": file.filename,
            "paper_id": paper_id,
            "pages": len(full_text),
            "text": cleaned[:5000],
            "full_length": len(cleaned),
            "rag_ready": True,
            "kg_enabled": kg_enabled,
            "kg_ready": kg_success,
            "kg_stats": kg_stats,
            "sections": section_info,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF extraction failed: {str(e)}")


def _extract_sections_from_text(text: str) -> dict:
    """
    Extract named sections from paper text.
    Returns {section_name: section_text}. Falls back to {"ALL": text} if none found.
    """
    section_pattern = re.compile(
        r"(?:^|\n)\s*(?P<name>"
        r"abstract|introduction|background|related work|methods?|methodology|approach"
        r"|experiments?|results?|discussion|conclusion|future work|references"
        r"|acknowledgments?|summary|materials?|implementation|evaluation"
        r"|findings|analysis|appendix|supplementary"
        r")\s*[:\n]",
        re.IGNORECASE,
    )

    matches = [(m.start(), m.group("name").strip()) for m in section_pattern.finditer(text)]

    if len(matches) < 2:
        return {"ALL": text}

    sections = {}
    for i, (start, name) in enumerate(matches):
        end = matches[i + 1][0] if i + 1 < len(matches) else len(text)
        section_text = text[start:end].strip()
        name_clean = name.strip().title()
        if len(section_text) > 100:
            sections[name_clean] = section_text

    return sections if sections else {"ALL": text}


def _clean_pdf_text(text: str) -> str:
    """Remove references section, extra whitespace, and non-ASCII garbage."""
    for pattern in [
        r"\n\s*References\s*\n.*",
        r"\n\s*Bibliography\s*\n.*",
        r"\n\s*REFERENCES\s*\n.*",
    ]:
        text = re.sub(pattern, "", text, flags=re.DOTALL)

    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"[^\x00-\x7F]+", " ", text)
    return text.strip()


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 4 — RAG (Retrieval Augmented Generation)
# ═══════════════════════════════════════════════════════════════════════════════

def _chunk_text(text: str, chunk_size: int = 600, overlap: int = 100) -> List[str]:
    """Split text into overlapping chunks preserving sentence boundaries."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks = []
    current_chunk: List[str] = []
    current_size = 0

    for sentence in sentences:
        words = sentence.split()
        word_count = len(words)

        if current_size + word_count > chunk_size and current_chunk:
            chunks.append(" ".join(current_chunk))
            overlap_words = current_chunk[-overlap:] if len(current_chunk) > overlap else current_chunk[:]
            current_chunk = overlap_words
            current_size = len(overlap_words)

        current_chunk.extend(words)
        current_size += word_count

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def _build_rag_index(text: str, source: str = "uploaded_pdf"):
    """Build FAISS index from text chunks."""
    global rag_index, rag_chunks, rag_metadata

    chunks = _chunk_text(text)
    if not chunks:
        return

    model = get_embedding_model()
    embeddings = np.array(model.encode(chunks, show_progress_bar=False)).astype("float32")
    faiss.normalize_L2(embeddings)

    dimension = embeddings.shape[1]
    rag_index = faiss.IndexFlatIP(dimension)
    rag_index.add(embeddings)

    rag_chunks = chunks
    rag_metadata = [{"source": source, "chunk_id": i} for i in range(len(chunks))]

    logger.info(f"RAG index built: {len(chunks)} chunks from '{source}'")


def _retrieve_chunks(query: str, top_k: int = 3) -> List[dict]:
    """Embed query and retrieve top-k relevant chunks from FAISS."""
    if rag_index is None or not rag_chunks:
        return []

    model = get_embedding_model()
    query_embedding = np.array(model.encode([query])).astype("float32")
    faiss.normalize_L2(query_embedding)

    scores, indices = rag_index.search(query_embedding, top_k)

    return [
        {"text": rag_chunks[idx], "score": float(score), "metadata": rag_metadata[idx]}
        for score, idx in zip(scores[0], indices[0])
        if idx < len(rag_chunks)
    ]


@app.get("/rag-status")
async def rag_status():
    """Check if RAG index is loaded."""
    return {
        "index_ready": rag_index is not None,
        "chunks": len(rag_chunks),
        "sources": list({m["source"] for m in rag_metadata}) if rag_metadata else [],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 5 — CHAT (RAG + Knowledge Graph)
# ═══════════════════════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    question: str
    context_text: Optional[str] = None
    use_kg: Optional[bool] = True


@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Chat endpoint.  Priority: Knowledge Graph → RAG → Abstract text.
    """
    global current_paper_id

    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    context = None
    sources: List[dict] = []
    context_source = None
    chunks_used = 0

    # ── Step 1: Knowledge Graph ───────────────────────────────────────────────
    if req.use_kg and current_paper_id and kg_manager and kg_manager.is_connected() and kg_builder:
        try:
            query_entities = kg_builder.extract_entities_for_query(question)
            kg_context = kg_manager.get_graph_context(current_paper_id, query_entities)

            if kg_context and kg_context.strip():
                context = kg_context
                context_source = "Knowledge Graph"
                logger.info("Using knowledge graph context")
            else:
                logger.info("KG returned no context, falling back to RAG")

        except Exception as e:
            logger.warning(f"Knowledge graph query failed: {e}")

    # ── Step 2: RAG fallback ──────────────────────────────────────────────────
    if context is None:
        retrieved = _retrieve_chunks(question, top_k=3)
        if retrieved:
            context = "\n\n---\n\n".join(r["text"] for r in retrieved)
            sources = [r["metadata"] for r in retrieved]
            context_source = "PDF (RAG)"
            chunks_used = len(retrieved)

    # ── Step 3: Abstract fallback ─────────────────────────────────────────────
    if context is None and req.context_text:
        context = req.context_text[:4000]
        sources = [{"source": "paper_abstract"}]
        context_source = "Abstract"

    if context is None:
        raise HTTPException(
            status_code=400,
            detail="No context available. Please upload a PDF first or provide context text.",
        )

    prompt = f"""You are an expert research assistant. Answer the question using ONLY the provided context.
If the answer is not in the context, say "I cannot find this in the provided paper."

Context:
{context}

Question: {question}

Give a clear, accurate answer based strictly on the context above."""

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=600,
        )
        answer = response.choices[0].message.content.strip()

        return {
            "answer": answer,
            "sources": sources,
            "context_source": context_source,
            "chunks_used": chunks_used,
            "kg_used": context_source == "Knowledge Graph",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# KNOWLEDGE GRAPH ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

def _require_kg() -> KnowledgeGraphManager:
    """Return the KG manager or raise 503 if unavailable."""
    kg_mgr = get_kg_manager()
    if not kg_mgr or not kg_mgr.is_connected():
        raise HTTPException(status_code=503, detail="Knowledge graph not available")
    return kg_mgr


@app.get("/kg-status")
async def kg_status():
    """Check knowledge graph system status."""
    kg_mgr = get_kg_manager()
    if kg_mgr is None:
        return {
            "enabled": False,
            "connected": False,
            "message": "Knowledge graph system not initialized",
            "kg_has_data": False,
        }
    if not kg_mgr.is_connected():
        return {
            "enabled": False,
            "connected": False,
            "message": "Neo4j database not connected. Ensure Neo4j is running.",
            "kg_has_data": False,
        }
    papers = kg_mgr.list_papers()
    return {
        "enabled": True,
        "connected": True,
        "papers": papers,
        "current_paper": current_paper_id,
        "paper_count": len(papers),
        "kg_has_data": len(papers) > 0,
    }


@app.get("/kg-papers")
async def kg_papers():
    """List all papers with knowledge graphs."""
    kg_mgr = _require_kg()
    papers = kg_mgr.list_papers()
    return {"papers": papers, "total": len(papers)}


@app.get("/kg-paper/{paper_id}")
async def kg_paper_info(paper_id: str):
    """Get knowledge graph summary for a specific paper."""
    kg_mgr = _require_kg()
    return kg_mgr.get_paper_summary(paper_id)


@app.delete("/kg-paper/{paper_id}")
async def delete_kg_paper(paper_id: str):
    """Delete a paper's knowledge graph."""
    global current_paper_id
    kg_mgr = _require_kg()
    success = kg_mgr.delete_paper_graph(paper_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete knowledge graph")
    if current_paper_id == paper_id:
        current_paper_id = None
    return {"message": f"Knowledge graph for '{paper_id}' deleted"}


@app.delete("/kg-all")
async def delete_all_kg():
    """Delete all papers from the knowledge graph."""
    kg_mgr = _require_kg()
    papers = kg_mgr.list_papers()
    failed = [p["paper_id"] for p in papers if not kg_mgr.delete_paper_graph(p["paper_id"])]
    if failed:
        return {"message": "Some papers could not be deleted", "failed": failed}
    return {"message": "All knowledge graph data cleared"}


@app.delete("/kg-wipe")
async def wipe_knowledge_graph():
    """Hard wipe — deletes ALL nodes and relationships from the graph database."""
    kg_mgr = _require_kg()
    success = kg_mgr.wipe_all()
    if not success:
        raise HTTPException(status_code=500, detail="Failed to wipe knowledge graph.")
    return {"message": "All nodes and relationships deleted from knowledge graph."}


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    kg_mgr = get_kg_manager()
    return {
        "status": "AI Research Assistant API running",
        "version": "1.0.0",
        "kg_enabled": kg_mgr is not None and kg_mgr.is_connected(),
    }


@app.get("/health")
async def health():
    kg_mgr = get_kg_manager()
    papers = kg_mgr.list_papers() if kg_mgr and kg_mgr.is_connected() else []
    return {
        "status": "ok",
        "rag_ready": rag_index is not None,
        "kg_ready": kg_mgr is not None and kg_mgr.is_connected(),
        "kg_has_data": len(papers) > 0,
    }
