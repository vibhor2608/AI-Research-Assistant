# Migration Guide: Adding KG to Existing main.py

This guide shows two ways to integrate knowledge graphs into your existing codebase:
1. **Safe Option**: Replace main.py with minimal risk
2. **Manual Option**: Merge changes into existing main.py

## Option 1: Safe Replacement (Recommended)

### Step 1: Backup Original
```bash
cd backend
cp main.py main_backup_original.py
```

### Step 2: Replace with KG Version
```bash
cp main_with_kg.py main.py
```

### Step 3: Verify Nothing Broke
```bash
# Start the server
uvicorn main:app --reload

# In another terminal, test endpoints
curl http://localhost:8000/
curl http://localhost:8000/health
curl http://localhost:8000/kg-status
```

### Step 4: Test Each Feature
```bash
# Discover papers (Phase 1 - unchanged)
curl "http://localhost:8000/papers?q=neural+networks"

# Summarize (Phase 2 - unchanged)
curl -X POST http://localhost:8000/summarize \
  -H "Content-Type: application/json" \
  -d '{"text":"Some paper text","title":"Title"}'

# Upload PDF (Phase 3 - now with KG!)
# Use web UI or:
curl -F "file=@paper.pdf" http://localhost:8000/upload-pdf

# Chat (Phase 4 - now with KG priority!)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"What methods are used?"}'
```

## Option 2: Manual Merge (Advanced)

If you've customized main.py and want to keep changes:

### Step 1: Copy New Files
```bash
cp neo4j_kg.py backend/
cp kg_builder.py backend/
```

### Step 2: Add Imports (at top of main.py)
```python
# Add these imports after existing imports:
import logging
from neo4j_kg import KnowledgeGraphManager, init_knowledge_graph_manager, get_kg_manager
from kg_builder import KnowledgeGraphBuilder

# Setup logging after imports:
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
```

### Step 3: Add Global Variables (after existing globals)
```python
# Add after existing rag_index, rag_chunks, etc.:

# ─── Knowledge Graph State ───────────────────────────────────────────────────
kg_manager = None
kg_builder = None
current_paper_id = None  # Track current paper for KG queries
```

### Step 4: Add Startup Event (add before/after existing events)
```python
@app.on_event("startup")
async def startup_event():
    """Initialize knowledge graph manager on startup."""
    global kg_manager, kg_builder
    
    logger.info("🚀 Starting up AI Research Assistant...")
    
    # Initialize knowledge graph manager
    kg_manager = init_knowledge_graph_manager()
    
    # Initialize knowledge graph builder
    kg_builder = KnowledgeGraphBuilder(groq_client)
    
    if kg_manager and kg_manager.is_connected():
        logger.info("✓ Knowledge graph system initialized")
    else:
        logger.warning("⚠ Knowledge graph system disabled (Neo4j not available)")
        logger.info("  To enable: Install Neo4j and set NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD in .env")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global kg_manager
    if kg_manager:
        kg_manager.close()
        logger.info("Knowledge graph connection closed")
```

### Step 5: Update `/upload-pdf` Endpoint

**Find** the existing `@app.post("/upload-pdf")` function.

**Replace the entire function** with:
```python
@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    """Extract text from uploaded PDF and build RAG + Knowledge Graph."""
    global current_paper_id
    
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    contents = await file.read()

    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        doc = fitz.open(tmp_path)
        full_text = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            full_text.append(page.get_text())

        doc.close()
        os.unlink(tmp_path)

        raw_text = "\n".join(full_text)

        # Clean text
        cleaned = _clean_pdf_text(raw_text)

        # Generate paper ID from filename
        paper_id = file.filename.replace(".pdf", "").replace(" ", "_").lower()
        current_paper_id = paper_id

        # Build RAG index from this PDF (existing functionality)
        _build_rag_index(cleaned, file.filename)

        # Build Knowledge Graph (new functionality)
        kg_success = False
        kg_stats = {"entities": 0, "relationships": 0}
        
        if kg_manager and kg_manager.is_connected() and kg_builder:
            try:
                logger.info(f"Building knowledge graph for {paper_id}...")
                
                # Extract entities and relationships
                entities, relationships = kg_builder.build_knowledge_graph(
                    cleaned, 
                    paper_id,
                    title=file.filename
                )
                
                # Create graph in Neo4j
                if entities and relationships:
                    kg_success = kg_manager.create_paper_graph(
                        paper_id,
                        file.filename,
                        entities,
                        relationships
                    )
                    kg_stats = {"entities": len(entities), "relationships": len(relationships)}
                    logger.info(f"Knowledge graph created: {kg_stats}")
            
            except Exception as e:
                logger.warning(f"Knowledge graph creation failed: {str(e)}")
                kg_success = False

        return {
            "filename": file.filename,
            "paper_id": paper_id,
            "pages": len(full_text),
            "text": cleaned[:5000],  # First 5000 chars for display
            "full_length": len(cleaned),
            "rag_ready": True,
            "kg_enabled": kg_manager is not None and kg_manager.is_connected(),
            "kg_ready": kg_success,
            "kg_stats": kg_stats,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF extraction failed: {str(e)}")
```

### Step 6: Update `/chat` Endpoint

**Find** the existing `@app.post("/chat")` function.

**Replace it** with this enhanced version:
```python
class ChatRequest(BaseModel):
    question: str
    context_text: Optional[str] = None  # For abstract-based chat without PDF
    use_kg: Optional[bool] = True  # Use knowledge graph if available


@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Enhanced chat endpoint with knowledge graph support.
    
    Priority: Knowledge Graph → RAG → Abstract
    """
    global current_paper_id, kg_manager, kg_builder
    
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    context = None
    sources = []
    context_source = None
    chunks_used = 0
    kg_context = None

    # Step 1: Try Knowledge Graph retrieval (if enabled)
    if req.use_kg and current_paper_id and kg_manager and kg_manager.is_connected() and kg_builder:
        try:
            logger.info(f"Querying knowledge graph for: {question}")
            
            # Extract entities from question
            query_entities = kg_builder.extract_entities_for_query(question)
            
            # Get graph context
            kg_context = kg_manager.get_graph_context(current_paper_id, query_entities)
            
            if kg_context and len(kg_context.strip()) > 0:
                context = kg_context
                context_source = "Knowledge Graph"
                logger.info("✓ Using knowledge graph context")
            else:
                logger.info("Knowledge graph returned no context, falling back to RAG")
        
        except Exception as e:
            logger.warning(f"Knowledge graph query failed: {str(e)}")

    # Step 2: Fallback to RAG retrieval
    if context is None:
        retrieved = _retrieve_chunks(question, top_k=3)
        
        if retrieved:
            context = "\n\n---\n\n".join([r["text"] for r in retrieved])
            sources = [r["metadata"] for r in retrieved]
            context_source = "PDF (RAG)"
            chunks_used = len(retrieved)
            logger.info("Using RAG context")

    # Step 3: Fallback to abstract context
    if context is None and req.context_text:
        context = req.context_text[:4000]
        sources = [{"source": "paper_abstract"}]
        context_source = "Abstract"

    # Return error if no context available
    if context is None:
        raise HTTPException(
            status_code=400,
            detail="No context available. Please upload a PDF first or provide context text.",
        )

    # Generate answer using Groq
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
```

### Step 7: Add KG Status Endpoint

**Add before the health check section**:
```python
# ═══════════════════════════════════════════════════════════════════════════════
# KNOWLEDGE GRAPH ENDPOINTS (NEW)
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/kg-status")
async def kg_status():
    """Check knowledge graph system status."""
    kg_mgr = get_kg_manager()
    
    if kg_mgr is None:
        return {
            "enabled": False,
            "connected": False,
            "message": "Knowledge graph system not initialized"
        }
    
    if not kg_mgr.is_connected():
        return {
            "enabled": False,
            "connected": False,
            "message": "Neo4j database not connected. Ensure Neo4j is running."
        }
    
    papers = kg_mgr.list_papers()
    
    return {
        "enabled": True,
        "connected": True,
        "papers": papers,
        "current_paper": current_paper_id,
        "paper_count": len(papers)
    }


@app.get("/kg-papers")
async def kg_papers():
    """Get list of all papers with knowledge graphs."""
    kg_mgr = get_kg_manager()
    
    if not kg_mgr or not kg_mgr.is_connected():
        raise HTTPException(status_code=503, detail="Knowledge graph not available")
    
    papers = kg_mgr.list_papers()
    return {"papers": papers, "total": len(papers)}


@app.get("/kg-paper/{paper_id}")
async def kg_paper_info(paper_id: str):
    """Get knowledge graph summary for a specific paper."""
    kg_mgr = get_kg_manager()
    
    if not kg_mgr or not kg_mgr.is_connected():
        raise HTTPException(status_code=503, detail="Knowledge graph not available")
    
    summary = kg_mgr.get_paper_summary(paper_id)
    return summary


@app.delete("/kg-paper/{paper_id}")
async def delete_kg_paper(paper_id: str):
    """Delete a paper's knowledge graph."""
    kg_mgr = get_kg_manager()
    
    if not kg_mgr or not kg_mgr.is_connected():
        raise HTTPException(status_code=503, detail="Knowledge graph not available")
    
    success = kg_mgr.delete_paper_graph(paper_id)
    
    if success:
        global current_paper_id
        if current_paper_id == paper_id:
            current_paper_id = None
        return {"message": f"Knowledge graph for {paper_id} deleted"}
    else:
        raise HTTPException(status_code=500, detail="Failed to delete knowledge graph")
```

### Step 8: Update Health Endpoint

**Find** the `/health` endpoint and update it:
```python
@app.get("/health")
async def health():
    kg_mgr = get_kg_manager()
    return {
        "status": "ok",
        "rag_ready": rag_index is not None,
        "kg_ready": kg_mgr is not None and kg_mgr.is_connected()
    }
```

### Step 9: Update Root Endpoint

**Find** the `/` endpoint and update:
```python
@app.get("/")
async def root():
    kg_mgr = get_kg_manager()
    return {
        "status": "AI Research Assistant API running",
        "version": "1.0.0",
        "kg_enabled": kg_mgr is not None and kg_mgr.is_connected()
    }
```

## Verification Checklist

After migration, verify everything works:

```bash
✓ Backend starts without errors
✓ /health returns status: "ok"
✓ /kg-status returns KG system status
✓ /papers endpoint works (discover papers)
✓ /summarize endpoint works
✓ /upload-pdf endpoint works (with KG stats)
✓ /chat endpoint works
✓ Neo4j connection works (check /kg-status)
```

## If Something Breaks

**Option 1: Restore Original**
```bash
cd backend
cp main_backup_original.py main.py
# Restart server
uvicorn main:app --reload
```

**Option 2: Debug**
Check logs for error messages and verify:
1. Neo4j is running and accessible
2. `.env` has correct credentials
3. All new files (neo4j_kg.py, kg_builder.py) are present
4. Dependencies installed: `pip install -r requirements.txt`

## Summary

Both options will work:
- **Option 1** (Safe): Fast, tested, 5 minutes
- **Option 2** (Manual): Keep customizations, 30 minutes

All existing functionality is preserved. New KG features are optional fallbacks.