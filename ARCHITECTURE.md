# Knowledge Graph System Architecture

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         User Interface (React)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │   Discover   │  │  Upload PDF  │  │  Deep Chat (with KG)     │  │
│  │   Papers     │  │  + Build KG  │  │  • Knowledge Graph       │  │
│  │              │  │              │  │  • RAG (fallback)        │  │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬─────────────┘  │
└─────────┼──────────────────┼────────────────────────┼────────────────┘
          │                  │                        │
          └──────────────────┼────────────────────────┘
                             │ HTTP
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      FastAPI Backend Server                          │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                    main.py (Enhanced)                          │ │
│  │  ┌──────────────┐        ┌────────────────────────────────┐  │ │
│  │  │ Phase 1-4    │        │ Phase 5: Knowledge Graph      │  │ │
│  │  │ (Existing)   │        │ (NEW)                          │  │ │
│  │  │              │        │                                │  │ │
│  │  │ • Discovery  │        │ ┌──────────────────────────┐  │  │ │
│  │  │ • Summarize  │◄──────►│ │ neo4j_kg.py              │  │  │ │
│  │  │ • RAG/FAISS  │        │ │ • Connection mgmt        │  │  │ │
│  │  │ • Chat       │        │ │ • CRUD operations        │  │  │ │
│  │  │              │        │ │ • Graph queries          │  │  │ │
│  │  └──────────────┘        │ └──────────────────────────┘  │  │ │
│  │                          │                                │  │ │
│  │                          │ ┌──────────────────────────┐  │  │ │
│  │                          │ │ kg_builder.py            │  │  │ │
│  │                          │ │ • Entity extraction      │  │  │ │
│  │                          │ │ • Relationship extract   │  │  │ │
│  │                          │ │ • Graph building         │  │  │ │
│  │                          │ └──────────────────────────┘  │  │ │
│  │                          │                                │  │ │
│  │  Enhanced Chat Flow      │ Priority Order:               │  │ │
│  │  ┌────────────────────┐  │ 1. Knowledge Graph (NEW)      │  │ │
│  │  │ User Question      │  │ 2. RAG/FAISS (Existing)      │  │ │
│  │  └────────┬───────────┘  │ 3. Abstract (Existing)       │  │ │
│  │           │              │                              │  │ │
│  │           ▼              │ All can fallback gracefully  │  │ │
│  │  ┌────────────────────┐  │                              │  │ │
│  │  │ Try KG Query       │──┼──────────────────────────────┘  │ │
│  │  └────────┬───────────┘  │                                │ │
│  │           │ (No match)   │                                │ │
│  │           ▼              │                                │ │
│  │  ┌────────────────────┐  │                                │ │
│  │  │ Try RAG Retrieval  │  │                                │ │
│  │  └────────┬───────────┘  │                                │ │
│  │           │ (No match)   │                                │ │
│  │           ▼              │                                │ │
│  │  ┌────────────────────┐  │                                │ │
│  │  │ Try Abstract       │  │                                │ │
│  │  └────────┬───────────┘  │                                │ │
│  │           │              │                                │ │
│  │           ▼              │                                │ │
│  │  ┌────────────────────┐  │                                │ │
│  │  │ Generate Answer    │  │                                │ │
│  │  │ (Groq LLM)         │  │                                │ │
│  │  └────────┬───────────┘  │                                │ │
│  │           │              │                                │ │
│  │           ▼              │                                │ │
│  │  ┌────────────────────┐  │                                │ │
│  │  │ Return Answer +    │  │                                │ │
│  │  │ context_source     │  │                                │ │
│  │  └────────────────────┘  │                                │ │
│  │                          │                                │ │
│  └──────────────────────────┴────────────────────────────────┘ │
│                   │                │                 │          │
└───────────────────┼────────────────┼─────────────────┼──────────┘
                    │                │                 │
                    ▼                ▼                 ▼
          ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
          │  Semantic    │  │   Neo4j      │  │   Groq API   │
          │  Scholar API │  │  Knowledge   │  │   (LLM)      │
          │              │  │  Graphs      │  │              │
          └──────────────┘  └──────────────┘  └──────────────┘
```

---

## Data Flow: PDF Upload with Knowledge Graph Creation

```
┌──────────────┐
│   User       │
│  Uploads     │
│   PDF        │
└──────┬───────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 1: PDF Received by Backend                            │
│ • Extract PDF file                                          │
│ • Read file contents into memory                            │
└──────┬────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 2: Text Extraction (PyMuPDF - fitz)                   │
│ • Read each page of PDF                                     │
│ • Extract text from pages                                   │
│ • Combine into raw text                                     │
│ Output: ~50-100 KB of text                                  │
└──────┬────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 3: Text Cleaning                                       │
│ • Remove References section                                 │
│ • Remove extra whitespace                                   │
│ • Remove non-ASCII characters                               │
│ • Normalize formatting                                      │
└──────┬────────────────────────────────────────────────────┘
       │
       ├─────────────────────┬──────────────────────┐
       │                     │                      │
       ▼                     ▼                      ▼
┌────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ Build RAG      │  │ Extract Entities │  │ Setup Paper ID   │
│ (Existing)     │  │ (LLM - Groq)     │  │                  │
│                │  │ (NEW)            │  │                  │
│ • Chunk text   │  │                  │  │ paper_id =       │
│ • Generate     │  │ Uses prompt:     │  │ filename_cleaned │
│   embeddings   │  │ "Extract key     │  │                  │
│ • Build FAISS  │  │  entities..."    │  └──────────────────┘
│   index        │  │                  │
│ ~5 seconds     │  │ Returns: [       │
└────────┬───────┘  │   {              │
         │          │    id: "bert",   │
         │          │    name: "BERT"  │
         │          │    type: "ALGO"  │
         │          │    ...           │
         │          │   },             │
         │          │   ...24 total    │
         │          │ ]                │
         │          │ ~25 seconds      │
         │          └────────┬─────────┘
         │                   │
         │                   ▼
         │          ┌──────────────────┐
         │          │ Extract Relations│
         │          │ (LLM - Groq)     │
         │          │ (NEW)            │
         │          │                  │
         │          │ Uses prompt:     │
         │          │ "Find how        │
         │          │  entities relate"│
         │          │                  │
         │          │ Returns: [       │
         │          │   {              │
         │          │    source: "bert"│
         │          │    target: "attn"│
         │          │    type: "USES"  │
         │          │   },             │
         │          │   ...18 total    │
         │          │ ]                │
         │          │ ~30 seconds      │
         │          └────────┬─────────┘
         │                   │
         │                   ▼
         │          ┌──────────────────┐
         │          │ Create Neo4j     │
         │          │ Graph            │
         │          │ (NEW)            │
         │          │                  │
         │          │ • Create Paper   │
         │          │   node           │
         │          │ • Create Entity  │
         │          │   nodes          │
         │          │ • Create Rel     │
         │          │   edges          │
         │          │ ~5 seconds       │
         │          └────────┬─────────┘
         │                   │
         └─────────┬─────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ Response to Frontend:                                       │
│ {                                                           │
│   "filename": "paper.pdf",                                  │
│   "paper_id": "paper",                                      │
│   "pages": 12,                                              │
│   "rag_ready": true,              ← Existing feature       │
│   "kg_enabled": true,              ← NEW                   │
│   "kg_ready": true,                ← NEW                   │
│   "kg_stats": {                    ← NEW                   │
│     "entities": 24,                                         │
│     "relationships": 18                                     │
│   }                                                         │
│ }                                                           │
└─────────────────────────────────────────────────────────────┘

Timeline:
Step 1 (PDF): < 1 second
Step 2 (Extract): 1-2 seconds
Step 3 (Clean): < 1 second
Step 4 (RAG): 5 seconds
Step 5 (Entities): 20-30 seconds
Step 6 (Relations): 20-35 seconds
Step 7 (Neo4j): 5 seconds
─────────────────────────────
Total: 50-75 seconds
```

---

## Data Flow: Question Answering with Knowledge Graph Priority

```
┌──────────────────────────────┐
│  User Asks Question:         │
│  "What is the main idea?"    │
└──────────┬───────────────────┘
           │
           ▼
┌────────────────────────────────────────┐
│ Backend Receives Question              │
│ {                                      │
│   "question": "What is the idea?",    │
│   "use_kg": true   (default)           │
│ }                                      │
└────────┬─────────────────────────────┘
         │
         ▼ STEP 1: Try Knowledge Graph
    ┌────────────────────────────────────────────┐
    │ Is Knowledge Graph Available & Connected?  │
    └────────┬──────────────────┬───────────────┘
      YES    │                  │ NO
            │                  │
            ▼                  │
    ┌──────────────────────┐   │
    │ Extract Query        │   │
    │ Entities Using LLM   │   │
    │                      │   │
    │ "What is the idea?"  │   │
    │   ↓                  │   │
    │ Query entities:      │   │
    │ ["main_idea",        │   │
    │  "concept",          │   │
    │  "topic"]            │   │
    └──────┬───────────────┘   │
           │                   │
           ▼                   │
    ┌──────────────────────┐   │
    │ Query Neo4j Graph    │   │
    │ for Entities Match   │   │
    │                      │   │
    │ MATCH entities WHERE │   │
    │ name contains        │   │
    │ "idea", "concept"    │   │
    └──────┬───────────────┘   │
           │                   │
    ┌──────┴──────┐            │
    │             │            │
  YES            NO            │
    │             │            │
    ▼             ▼            ▼
 Found      Not Found   Fallback to
Context    Context      STEP 2
    │             │
    │             └──────────┐
    │                        │
    └────────────┬───────────┘
                 │
                 ▼ STEP 2: Fallback to RAG
        ┌──────────────────────────────────────┐
        │ Is FAISS RAG Index Available?        │
        └────────┬──────────────────┬──────────┘
          YES    │                  │ NO
                │                  │
                ▼                  │
        ┌──────────────────────┐   │
        │ Embed Question       │   │
        │ (SentenceTransformer)│   │
        │                      │   │
        │ "What is the idea?"  │   │
        │   ↓                  │   │
        │ [0.23, 0.45, ...]   │   │
        └──────┬───────────────┘   │
               │                   │
               ▼                   │
        ┌──────────────────────┐   │
        │ Search FAISS         │   │
        │ Top-3 similar chunks │   │
        │                      │   │
        │ Chunk 1: "The main   │   │
        │ idea is..."          │   │
        │ Chunk 2: "Based on..." │  │
        │ Chunk 3: "This work..." │ │
        └──────┬───────────────┘   │
               │                   │
        ┌──────┴──────┐            │
        │             │            │
      YES            NO            │
        │             │            │
        ▼             ▼            ▼
     Found      Not Found   Fallback to
    Chunks      Chunks      STEP 3
        │             │
        │             └──────────┐
        │                        │
        └────────────┬───────────┘
                     │
                     ▼ STEP 3: Fallback to Abstract
            ┌────────────────────────────┐
            │ Is Abstract Text Available?│
            └────────┬──────────────────┬┘
              YES    │                  │ NO
                    │                  │
                    ▼                  ▼
            ┌──────────────────┐    Error:
            │ Use Abstract     │    "No context
            │ (up to 4000 chars)    available"
            └──────┬───────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
        ▼                     │
   All branches              │
   converge here:            │
        │                     │
        └──────────┬──────────┘
                   │
                   ▼
    ┌────────────────────────────────────────────┐
    │ Generate Answer Using Groq LLM             │
    │                                            │
    │ Prompt:                                    │
    │ "You are expert. Answer ONLY using        │
    │  this context:                             │
    │  Context: [gathered from KG/RAG/Abstract] │
    │  Question: What is the main idea?"        │
    │                                            │
    │ LLM generates answer: "The main idea..." │
    └──────┬───────────────────────────────────┘
           │
           ▼
    ┌────────────────────────────────────────────┐
    │ Return Response to Frontend:               │
    │ {                                          │
    │   "answer": "The main idea...",           │
    │   "context_source": "Knowledge Graph",    │
    │   "kg_used": true,                        │
    │   "chunks_used": 0,                       │
    │   "sources": []                           │
    │ }                                          │
    └────────────────────────────────────────────┘
           │
           ▼
    ┌──────────────────────────────────────┐
    │ Response sent to Frontend            │
    │ "context_source" shows which method: │
    │ • Knowledge Graph (NEW)               │
    │ • PDF (RAG) (Existing)                │
    │ • Abstract (Existing)                 │
    └──────────────────────────────────────┘
```

---

## Entity Extraction Pipeline

```
Raw Paper Text (50-100 KB)
  │
  ▼
┌──────────────────────────────────────────────────────┐
│ Truncate to 8000 characters (LLM limit)             │
└──────┬───────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────┐
│ Groq LLM Prompt:                                    │
│ "Extract key entities from this paper...            │
│  Return JSON with:                                   │
│  - id (lowercase_id)                                 │
│  - name (Human Readable Name)                        │
│  - type (CONCEPT|METHOD|ALGORITHM|DATASET|          │
│           METRIC|AUTHOR|TOOL|RESULT)               │
│  - description (1-2 sentences)"                      │
│                                                      │
│ Model: llama-3.1-8b-instant                         │
│ Temperature: 0.3 (consistent)                        │
│ Max tokens: 2000                                     │
│ Time: 10-30 seconds                                  │
└──────┬───────────────────────────────────────────────┘
       │
       ▼
    Returns:
    [
      {
        id: "bert",
        name: "BERT",
        type: "ALGORITHM",
        description: "Bidirectional Encoder Representations from Transformers..."
      },
      {
        id: "transformer",
        name: "Transformer",
        type: "ALGORITHM",
        description: "Architecture based on self-attention mechanisms..."
      },
      ...24 total entities
    ]
       │
       ▼
┌──────────────────────────────────────────────────────┐
│ Store in Neo4j as Entity Nodes:                     │
│                                                      │
│ CREATE (e:Entity)                                   │
│ SET e.entity_id = "paper_id_bert"                   │
│ SET e.name = "BERT"                                 │
│ SET e.type = "ALGORITHM"                            │
│ SET e.description = "..."                           │
│ MERGE (e)-[:IN_PAPER]->(p:Paper)                    │
└──────────────────────────────────────────────────────┘
```

---

## Relationship Extraction Pipeline

```
Extracted Entities (e.g., 24 entities)
  │
  ├─ BERT
  ├─ Transformer
  ├─ Self-Attention
  ├─ Parallel Processing
  ├─ NLP
  └─ ...
  │
  ▼
┌──────────────────────────────────────────────────────┐
│ Groq LLM Prompt:                                    │
│ "Given these entities and the paper text,           │
│  extract relationships between them...              │
│  Return JSON with:                                   │
│  - source (entity_id)                                │
│  - target (entity_id)                                │
│  - type (USES|IMPROVES|IMPLEMENTS|COMPARES_WITH|    │
│           RELATES_TO|BASED_ON|EXTENDS|APPLIES_TO)  │
│  - description (1-2 sentences)"                      │
│                                                      │
│ Only valid source/target from provided entities     │
│ Model: llama-3.1-8b-instant                         │
│ Temperature: 0.3                                     │
│ Max tokens: 2000                                     │
│ Time: 20-40 seconds                                  │
└──────┬───────────────────────────────────────────────┘
       │
       ▼
    Returns:
    [
      {
        source: "bert",
        target: "transformer",
        type: "USES",
        description: "BERT uses the Transformer architecture..."
      },
      {
        source: "bert",
        target: "self_attention",
        type: "IMPLEMENTS",
        description: "BERT implements self-attention mechanisms..."
      },
      ...18 total relationships (validated)
    ]
       │
       ▼
┌──────────────────────────────────────────────────────┐
│ Validate Relationships:                             │
│ For each relationship:                               │
│  - Verify source ID in valid_entity_ids ✓           │
│  - Verify target ID in valid_entity_ids ✓           │
│  - Discard invalid relationships                     │
│                                                      │
│ Result: ~18 valid relationships                     │
└──────┬───────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────┐
│ Store in Neo4j as Relationship Edges:              │
│                                                      │
│ MATCH (e1:Entity {entity_id: "paper_bert"})        │
│ MATCH (e2:Entity {entity_id: "paper_transformer"}) │
│ MERGE (e1)-[r:RELATED {rel_type: "USES"}]->(e2)   │
│ SET r.description = "..."                           │
└──────────────────────────────────────────────────────┘
```

---

## Neo4j Graph Structure Per Paper

```
Paper Node:
┌──────────────────────────────┐
│ Paper                        │
│ {                            │
│   paper_id: "bert"           │
│   filename: "bert.pdf"       │
│   created_at: timestamp      │
│   updated_at: timestamp      │
│ }                            │
└────────────┬─────────────────┘
             │
    ┌────────┴────────┐
    │                 │
    ▼                 ▼
Entity Nodes:      Entity Nodes:
┌──────────────┐  ┌──────────────┐
│ Entity       │  │ Entity       │
│ {            │  │ {            │
│ entity_id:   │  │ entity_id:   │
│ "paper_bert" │  │ "paper_trf"  │
│ name: "BERT" │  │ name: "XFR"  │
│ type: "ALGO" │  │ type: "ALGO" │
│ }            │  │ }            │
└────┬─────────┘  └────┬─────────┘
     │                 │
     └────┬────────────┘
          │
          ▼
      (USES)
     Relationship
    Edge with:
    - rel_type: "USES"
    - description: "BERT uses..."

Complete Paper Graph:
  ┌─── Entity ──────┐
  │     (BERT)      │
  │                 │
  │  Uses ───┐      │
  │  Based   │      │
  │  On  ←───┼──┐   │
  │           │  │   │
  │    ┌──────┘  │   │
  │    ▼         │   │
  │  Entity      │   │
  │  (Trans)     │   │
  │              │   │
  │ Extends ──┐  │   │
  │           │  │   │
  │      ┌────┘  │   │
  │      ▼       │   │
  │   Entity     │   │
  │   (RNN) ◄────┘   │
  │                  │
  └──────────────────┘
  
  (Simplified: Actually 20-30 entities
   with 15-20 relationships)
```

---

## System Health & Monitoring

```
┌──────────────────────────────────────────────┐
│ Health Check Endpoints                       │
└──────┬───────────────────────────────────────┘
       │
       ├─ GET /health
       │  └─ Returns: RAG & KG status
       │     {
       │       "status": "ok",
       │       "rag_ready": true,
       │       "kg_ready": true
       │     }
       │
       ├─ GET /kg-status
       │  └─ Returns: KG system info
       │     {
       │       "enabled": true,
       │       "connected": true,
       │       "papers": [...],
       │       "current_paper": "paper_id",
       │       "paper_count": 5
       │     }
       │
       ├─ GET /kg-papers
       │  └─ Returns: All papers with graphs
       │     {
       │       "papers": [
       │         {
       │           "paper_id": "bert",
       │           "filename": "bert.pdf",
       │           "entity_count": 24
       │         }
       │       ]
       │     }
       │
       ├─ GET /kg-paper/{id}
       │  └─ Returns: Paper graph stats
       │     {
       │       "paper_id": "bert",
       │       "entity_count": 24,
       │       "relationship_count": 18
       │     }
       │
       └─ DELETE /kg-paper/{id}
          └─ Deletes paper graph
             {
               "message": "Graph deleted"
             }

Status Meanings:
┌─────────────────────────────────────┐
│ enabled: true                       │
│ connected: true                     │
│ → Neo4j working, KG ready           │
│                                     │
│ enabled: true                       │
│ connected: false                    │
│ → Neo4j configured but unavailable  │
│ → Falls back to RAG (works fine)    │
│                                     │
│ enabled: false                      │
│ → KG system disabled                │
│ → Uses RAG only                     │
└─────────────────────────────────────┘
```

---

## Graceful Degradation Flow

```
System Starting
  │
  ├─ Initialize RAG (FAISS)
  │  │
  │  └─ ✓ Success
  │
  ├─ Initialize KG Manager
  │  │
  │  ├─ Connect to Neo4j
  │  │  │
  │  │  ├─ ✓ Connected
  │  │  │  └─ KG System ENABLED
  │  │  │
  │  │  └─ ✗ Connection Failed
  │  │     └─ Log warning: "Neo4j unavailable"
  │  │
  │  └─ KG System DISABLED (but RAG works)
  │
  └─ Initialize KG Builder (LLM)
     │
     └─ ✓ Ready (uses Groq client)

System Running with PDF Upload:
  │
  ├─ Extract text ✓
  ├─ Build RAG index ✓
  │
  ├─ Try to build KG
  │  │
  │  ├─ KG enabled?
  │  │  ├─ YES
  │  │  │  └─ Build KG (may fail)
  │  │  │     ├─ Extract entities
  │  │  │     ├─ Extract relationships
  │  │  │     └─ Create graph
  │  │  │
  │  │  └─ NO
  │  │     └─ Skip (RAG only mode)
  │  │
  │  └─ KG Error?
  │     ├─ YES: Log warning, continue
  │     └─ NO: Graph created ✓
  │
  └─ Return response
     ├─ rag_ready: true (always)
     ├─ kg_enabled: true/false
     ├─ kg_ready: true/false
     └─ kg_stats: {...} if enabled

System Running with Chat:
  │
  ├─ Question received
  │
  ├─ Try KG?
  │  ├─ KG not enabled → Skip
  │  ├─ KG enabled?
  │  │  ├─ YES
  │  │  │  ├─ Query graph
  │  │  │  ├─ Found context?
  │  │  │  │  ├─ YES → Use KG
  │  │  │  │  └─ NO → Continue
  │  │  │  └─ KG Error → Continue
  │  │  └─ NO → Continue
  │  │
  │  └─ KG not used
  │
  ├─ Try RAG?
  │  ├─ RAG available?
  │  │  ├─ YES
  │  │  │  ├─ Query FAISS
  │  │  │  ├─ Found chunks?
  │  │  │  │  ├─ YES → Use RAG
  │  │  │  │  └─ NO → Continue
  │  │  │  └─ RAG Error → Continue
  │  │  └─ NO → Continue
  │  │
  │  └─ RAG not used
  │
  ├─ Try Abstract?
  │  ├─ Abstract available?
  │  │  ├─ YES → Use Abstract
  │  │  └─ NO → Error
  │  │
  │  └─ No context: Error
  │
  └─ Generate answer (context from above)
     └─ Return with context_source
```

---

**This architecture ensures reliability and graceful degradation at every level.**