# Knowledge Graph Integration Guide

This guide explains how to integrate Neo4j knowledge graph functionality into the existing AI Research Assistant project.

## Overview

The knowledge graph feature adds semantic understanding of research papers by:
1. Extracting key entities (concepts, methods, algorithms, datasets, etc.) from papers
2. Extracting relationships between entities
3. Storing them in a Neo4j knowledge graph
4. Querying the graph for intelligent information retrieval

## Files Added

### Backend Files
1. **neo4j_kg.py** - Neo4j connection and knowledge graph management
   - Manages Neo4j connections
   - CRUD operations for knowledge graphs
   - Query execution on graphs
   - Error handling and fallbacks

2. **kg_builder.py** - Knowledge graph construction from papers
   - Entity extraction using Groq LLM
   - Relationship extraction using Groq LLM
   - Query entity extraction for user questions
   - Graph building orchestration

3. **main_with_kg.py** - Enhanced main.py with KG integration
   - Startup/shutdown hooks for KG initialization
   - Enhanced `/upload-pdf` endpoint for KG creation
   - Enhanced `/chat` endpoint with KG query priority
   - New KG endpoints: `/kg-status`, `/kg-papers`, `/kg-paper/{id}`, etc.

4. **requirements_updated.txt** - Updated dependencies
   - Added: `neo4j==5.14.0`
   - Added: `python-dotenv==1.0.0`

## Setup Instructions

### Step 1: Install Neo4j

#### Option A: Local Installation (Recommended for Development)
```bash
# Windows - Download from: https://neo4j.com/download/
# Run the installer and follow prompts
# Default URI: bolt://localhost:7687
# Default user: neo4j
# Default password: password (change this!)

# Or use Docker:
docker run --name neo4j -d -p 7687:7687 -p 7474:7474 \
  -e NEO4J_AUTH=neo4j/mypassword \
  neo4j:latest
```

#### Option B: Cloud (Neo4j Aura)
1. Go to https://neo4j.com/cloud/aura/
2. Create a free account
3. Create a database
4. Copy the connection details

### Step 2: Update Backend Files

Replace the original `main.py` with `main_with_kg.py`:
```bash
cd backend
# Backup original
cp main.py main_backup.py
# Use the new version
cp main_with_kg.py main.py
```

Or manually merge the changes into your existing `main.py` by:
1. Adding imports: `from neo4j_kg import ...` and `from kg_builder import ...`
2. Adding global state variables for KG
3. Adding startup/shutdown events
4. Modifying `/upload-pdf` endpoint (see below)
5. Modifying `/chat` endpoint (see below)
6. Adding new `/kg-*` endpoints

### Step 3: Update Dependencies

```bash
cd backend

# Option 1: Replace requirements.txt
cp requirements_updated.txt requirements.txt

# Option 2: Or add manually to existing requirements.txt
pip install neo4j==5.14.0 python-dotenv==1.0.0
```

Then install:
```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment

Edit `backend/.env` and add Neo4j credentials:
```env
GROQ_API_KEY=your_key_here

# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
```

### Step 5: Test the Integration

1. Start the backend:
```bash
cd backend
uvicorn main:app --reload
```

2. Check KG status:
```bash
curl http://localhost:8000/kg-status
```

Expected response:
```json
{
  "enabled": true,
  "connected": true,
  "papers": [],
  "current_paper": null,
  "paper_count": 0
}
```

3. Upload a PDF and check the response:
- Should include `"kg_enabled": true` and `"kg_ready": true`
- Should show entity and relationship counts

## How It Works

### Upload Flow
```
User uploads PDF
  ↓
Extract text (existing RAG)
  ↓
Build RAG index (existing)
  ↓
Extract entities using LLM
  ↓
Extract relationships using LLM
  ↓
Create Neo4j knowledge graph (NEW)
  ↓
Return response with KG stats
```

### Chat Flow (Priority Order)
```
User asks question
  ↓
1. Query Knowledge Graph (NEW)
   If found, use KG context
  ↓
2. Fallback to FAISS RAG (existing)
   If found, use RAG chunks
  ↓
3. Fallback to Abstract (existing)
   If provided, use abstract context
  ↓
4. Generate answer using Groq LLM
```

## API Endpoints

### New Knowledge Graph Endpoints

**GET /kg-status**
- Check if KG system is enabled and connected
- See list of papers with graphs

**GET /kg-papers**
- Get all papers with knowledge graphs

**GET /kg-paper/{paper_id}**
- Get summary for a specific paper graph
- Returns entity and relationship counts

**DELETE /kg-paper/{paper_id}**
- Delete a paper's knowledge graph

### Enhanced Endpoints

**POST /upload-pdf**
- Now includes KG building in response:
```json
{
  "kg_enabled": true,
  "kg_ready": true,
  "kg_stats": {
    "entities": 24,
    "relationships": 18
  }
}
```

**POST /chat**
- Now supports knowledge graph queries
- Returns `"kg_used": true` if KG was used
- Falls back to RAG if KG has no relevant context
```json
{
  "answer": "...",
  "context_source": "Knowledge Graph",
  "kg_used": true,
  "chunks_used": 0
}
```

**GET /health**
- Now includes KG status:
```json
{
  "status": "ok",
  "rag_ready": true,
  "kg_ready": true
}
```

## Entity Types Extracted

- **CONCEPT**: Abstract ideas and theories
- **METHOD**: Approaches and techniques
- **ALGORITHM**: Specific algorithms
- **DATASET**: Data used in the paper
- **METRIC**: Evaluation metrics
- **AUTHOR**: Person names
- **TOOL**: Software libraries and tools
- **RESULT**: Outcomes and findings

## Relationship Types

- **USES**: Entity A uses entity B
- **IMPROVES**: A improves on B
- **IMPLEMENTS**: A implements B
- **COMPARES_WITH**: A compared with B
- **RELATES_TO**: General relationship
- **BASED_ON**: A builds on B
- **EXTENDS**: A extends B
- **APPLIES_TO**: A applies to B

## Multiple Papers Support

Each uploaded paper:
1. Gets a unique `paper_id` (derived from filename)
2. Creates a separate knowledge graph in Neo4j
3. Has its own set of entities and relationships
4. Can be queried independently

Switch between papers:
- Upload new PDF → `current_paper_id` updates
- Query uses the current paper's graph
- View all papers via `/kg-papers` endpoint

Delete a paper:
- Use `/kg-paper/{paper_id}` DELETE endpoint
- Removes graph from Neo4j
- Clears from memory if it's current

## Fallback Behavior

The system is designed to gracefully degrade:

1. **If Neo4j not connected**
   - KG features disabled
   - System works with RAG only
   - No errors in user experience

2. **If KG query returns nothing**
   - Automatically falls back to RAG
   - User gets answer from FAISS chunks

3. **If both KG and RAG fail**
   - Falls back to abstract context
   - Or returns "no context available" error

## Performance Considerations

### Entity Extraction
- Uses Groq LLM (fast, reliable)
- Takes ~10-30 seconds per paper
- Limited to 8000 characters of text

### Relationship Extraction
- Careful entity validation
- Only creates valid relationships
- Takes ~15-40 seconds per paper

### Graph Queries
- Uses Neo4j's efficient indexing
- Real-time retrieval
- Scalable to thousands of papers

### Storage
- Entities and relationships stored in Neo4j
- Efficient graph database
- Query results cached in memory during session

## Troubleshooting

### Neo4j Connection Failed
```
⚠ Neo4j connection failed: ...
```
**Solution:**
1. Check Neo4j is running: `neo4j status` (or Docker dashboard)
2. Verify credentials in `.env`
3. Check URI format (should be `bolt://localhost:7687`)

### "No entities extracted"
- Paper text too short or unclear
- LLM couldn't identify key concepts
- Falls back to RAG automatically (no issue)

### "Knowledge graph query returned no context"
- Query entities don't match paper entities
- Falls back to RAG automatically

### Performance Issues
- Try reducing `max_chars` in entity extraction
- Limit to shorter papers initially
- Consider batch processing

## Limitations & Future Work

### Current Limitations
- Entities extracted from paper text only
- No cross-paper relationships yet
- In-memory state lost on restart
- Single paper active at a time for RAG

### Future Enhancements
1. **Cross-Paper Relationships**
   - Link entities across papers
   - Build research domain graphs

2. **Persistent Storage**
   - Save graph state to disk
   - Resume from checkpoints

3. **Multi-Paper Active State**
   - Query multiple papers simultaneously
   - Aggregate results

4. **Advanced Analytics**
   - Citation network analysis
   - Research trend detection
   - Author collaboration graphs

5. **UI Enhancements**
   - Visualize knowledge graph
   - Interactive graph exploration
   - Filter by entity type

## Code Integration Examples

### Minimal Integration (Existing main.py)
```python
# Add at top
from neo4j_kg import init_knowledge_graph_manager
from kg_builder import KnowledgeGraphBuilder

# In startup event
@app.on_event("startup")
async def startup():
    kg_manager = init_knowledge_graph_manager()
    kg_builder = KnowledgeGraphBuilder(groq_client)

# In upload endpoint
kg_manager.create_paper_graph(paper_id, filename, entities, relationships)

# In chat endpoint
context = kg_manager.get_graph_context(paper_id, query_entities)
```

### Full Integration
Use the provided `main_with_kg.py` which has complete implementation.

## Support & Questions

For issues or questions:
1. Check Neo4j connection status: `/kg-status`
2. Review logs for error messages
3. Verify `.env` configuration
4. Check Neo4j web interface: `localhost:7474`

## License & Attribution

Built with:
- Neo4j (Graph Database)
- Groq API (LLM)
- FastAPI (Web Framework)
- Sentence Transformers (Embeddings)
- FAISS (Vector Search)