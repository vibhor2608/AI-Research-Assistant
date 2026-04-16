# Knowledge Graph Implementation Checklist

## Pre-Implementation Checklist

- [ ] Read through KG_SUMMARY.md (5 minutes)
- [ ] Read through KG_QUICK_START.md (5 minutes)
- [ ] Have existing project backed up
- [ ] Have Groq API key ready
- [ ] Decide on Neo4j deployment (local, Docker, or cloud)

## Phase 1: Neo4j Setup (10-15 minutes)

### Option A: Docker (Recommended - Easiest)
- [ ] Docker installed on your system
- [ ] Run Neo4j container:
  ```bash
  docker run --name neo4j -d -p 7687:7687 -p 7474:7474 \
    -e NEO4J_AUTH=neo4j/mypassword \
    neo4j:latest
  ```
- [ ] Verify Neo4j is running: `docker ps | grep neo4j`
- [ ] Access web interface: http://localhost:7474
- [ ] Login with neo4j / mypassword
- [ ] Neo4j is ready ✓

### Option B: Local Installation
- [ ] Download Neo4j from https://neo4j.com/download/
- [ ] Run installer
- [ ] Start Neo4j service
- [ ] Access web interface: http://localhost:7474
- [ ] Note your password
- [ ] Neo4j is ready ✓

### Option C: Neo4j Cloud (Aura)
- [ ] Create account at https://neo4j.com/cloud/aura/
- [ ] Create free database
- [ ] Copy connection string and credentials
- [ ] Note URI, username, password
- [ ] Neo4j is ready ✓

## Phase 2: Backend File Setup (10 minutes)

### Copy New Python Files
- [ ] Create backup: `cp main.py main_backup.py`
- [ ] Copy `neo4j_kg.py` to `backend/`
- [ ] Copy `kg_builder.py` to `backend/`
- [ ] Copy `main_with_kg.py` to `backend/`

### Replace Main Application
Choose ONE approach:

#### Approach A: Complete Replacement (Easier)
- [ ] Verify `main_with_kg.py` is in backend/
- [ ] Replace: `cp main_with_kg.py main.py`
- [ ] Go to Phase 3

#### Approach B: Manual Merge (Advanced)
- [ ] Read MIGRATION_GUIDE.md carefully
- [ ] Follow step-by-step instructions
- [ ] Verify all sections added
- [ ] Go to Phase 3

### Update Dependencies
- [ ] Add neo4j==5.14.0 to requirements.txt
- [ ] Add python-dotenv==1.0.0 to requirements.txt
- [ ] Or use provided requirements_updated.txt
- [ ] Verify both added:
  ```bash
  grep neo4j requirements.txt
  grep python-dotenv requirements.txt
  ```

## Phase 3: Environment Configuration (5 minutes)

### Update .env File
- [ ] Open `backend/.env`
- [ ] Add (or update) Neo4j credentials:
  ```env
  NEO4J_URI=bolt://localhost:7687
  NEO4J_USER=neo4j
  NEO4J_PASSWORD=your_password
  ```
- [ ] Verify GROQ_API_KEY is still present
- [ ] Save file

### Verify Credentials
- [ ] URI format correct (bolt://...)
- [ ] Username matches Neo4j setup
- [ ] Password is correct
- [ ] No extra spaces

## Phase 4: Python Dependencies (5 minutes)

### Install New Packages
```bash
cd backend
pip install neo4j==5.14.0 python-dotenv==1.0.0
```

### Verify Installation
- [ ] Run without errors
- [ ] Check installation:
  ```bash
  python -c "import neo4j; print(neo4j.__version__)"
  python -c "import dotenv; print(dotenv.__version__)"
  ```

## Phase 5: Backend Startup Test (5 minutes)

### Start Backend Server
```bash
cd backend
uvicorn main:app --reload
```

### Monitor Startup Logs
- [ ] Server starts without errors
- [ ] Look for these logs:
  ```
  INFO:     Uvicorn running on http://0.0.0.0:8000
  INFO:     Application startup complete
  INFO:     ✓ Knowledge graph system initialized
  ```
- [ ] If warning about Neo4j unavailable - that's OK (can still use RAG)
- [ ] Server is running ✓

## Phase 6: Health Checks (10 minutes)

### Test 1: API Health Endpoint
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "ok",
  "rag_ready": true,
  "kg_ready": true  // or false if Neo4j unavailable
}
```

- [ ] Status is "ok"
- [ ] rag_ready is true
- [ ] kg_ready shows correct status

### Test 2: Knowledge Graph Status
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

- [ ] enabled is true
- [ ] connected is true (if Neo4j running)
- [ ] papers is empty list (no papers uploaded yet)

### Test 3: Root Endpoint
```bash
curl http://localhost:8000/
```

Expected response includes:
```json
{
  "kg_enabled": true
}
```

- [ ] kg_enabled shows correct status

## Phase 7: Existing Feature Tests (10 minutes)

### Test 4: Paper Discovery (Unchanged)
```bash
curl "http://localhost:8000/papers?q=neural+networks&limit=5"
```

- [ ] Returns papers
- [ ] No errors
- [ ] All existing functionality works ✓

### Test 5: Summarization (Unchanged)
```bash
curl -X POST http://localhost:8000/summarize \
  -H "Content-Type: application/json" \
  -d '{"text":"Some research content","title":"Test"}'
```

- [ ] Returns summary JSON
- [ ] No errors
- [ ] Works as before ✓

## Phase 8: PDF Upload & KG Test (5-10 minutes)

### Test 6: Upload PDF with KG
Use the web UI:
1. [ ] Open http://localhost:5173
2. [ ] Go to "Upload PDF" tab
3. [ ] Drag-and-drop a research PDF
4. [ ] Wait for processing (30-40 seconds)
5. [ ] Check response for:
   ```json
   {
     "rag_ready": true,
     "kg_enabled": true,
     "kg_ready": true,
     "kg_stats": {
       "entities": 20,
       "relationships": 15
     }
   }
   ```

- [ ] File uploaded successfully
- [ ] Processing completed
- [ ] kg_stats shows entities and relationships
- [ ] No errors in console

### Alternative: curl Test
```bash
curl -F "file=@your_paper.pdf" http://localhost:8000/upload-pdf
```

- [ ] Upload successful
- [ ] Response includes kg_stats
- [ ] Entity count > 0
- [ ] Relationship count > 0

## Phase 9: Knowledge Graph Query Test (5 minutes)

### Test 7: Check Uploaded Papers
```bash
curl http://localhost:8000/kg-papers
```

Expected response:
```json
{
  "papers": [
    {
      "paper_id": "your_paper",
      "filename": "your_paper.pdf",
      "entity_count": 20
    }
  ],
  "total": 1
}
```

- [ ] Paper appears in list
- [ ] Entity count matches upload response
- [ ] Relationship count shows

### Test 8: Get Paper Details
```bash
curl http://localhost:8000/kg-paper/your_paper
```

Expected response:
```json
{
  "paper_id": "your_paper",
  "entity_count": 20,
  "relationship_count": 15
}
```

- [ ] Paper details returned
- [ ] Counts match expectations

## Phase 10: Chat Test with KG (5 minutes)

### Test 9: Chat with KG-Enabled Answer
Use the web UI:
1. [ ] Go to "Deep Chat" tab
2. [ ] Type a question about the paper
3. [ ] Check response for:
   ```json
   {
     "answer": "...",
     "context_source": "Knowledge Graph",
     "kg_used": true,
     "chunks_used": 0
   }
   ```

- [ ] Question answered
- [ ] context_source shows where answer came from
- [ ] kg_used is true (if KG was used)

### Alternative: curl Test
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"What is the main focus of this paper?"}'
```

- [ ] Chat responds with answer
- [ ] Response includes context_source
- [ ] No errors

## Phase 11: Fallback Test (5 minutes)

### Test 10: RAG Fallback (when KG doesn't find answer)
1. [ ] Ask a very specific question not in entities
2. [ ] Check if it falls back to RAG
3. [ ] context_source should be "PDF (RAG)"

### Test 11: Multiple Papers
1. [ ] Upload second PDF
2. [ ] Check /kg-papers shows 2 papers
3. [ ] Chat uses new paper's graph
4. [ ] Delete first paper: `curl -X DELETE http://localhost:8000/kg-paper/first_paper`
5. [ ] Verify deletion in /kg-papers

## Phase 12: Neo4j Verification (Optional but Recommended)

### Inspect Neo4j Database
1. [ ] Open http://localhost:7474
2. [ ] Login with your credentials
3. [ ] Run query:
   ```cypher
   MATCH (p:Paper) RETURN p
   ```
4. [ ] See paper nodes
5. [ ] Run query:
   ```cypher
   MATCH (e:Entity) RETURN e LIMIT 10
   ```
6. [ ] See extracted entities
7. [ ] Run query:
   ```cypher
   MATCH (e1:Entity)-[r:RELATED]->(e2:Entity) RETURN e1, r, e2 LIMIT 5
   ```
8. [ ] See relationships between entities

## Final Verification Checklist

### System Status
- [ ] Backend starts without errors
- [ ] All health endpoints return OK
- [ ] Neo4j connected (if available)
- [ ] KG system enabled

### Existing Features (Must Still Work)
- [ ] Paper discovery ✓
- [ ] Paper summarization ✓
- [ ] RAG chat ✓
- [ ] PDF upload ✓

### New Features (Should Work)
- [ ] KG building on upload ✓
- [ ] KG chat with proper context source ✓
- [ ] Multiple papers support ✓
- [ ] Paper management endpoints ✓

### Error Handling
- [ ] System works if Neo4j unavailable (RAG fallback)
- [ ] System works with partial data (graceful degradation)
- [ ] Error messages are helpful
- [ ] No breaking changes

## Rollback Procedure (If Needed)

### Quick Rollback
```bash
cd backend
cp main_backup.py main.py
# Restart backend
uvicorn main:app --reload
```

- [ ] Backend starts
- [ ] All features work as before
- [ ] KG system disabled (OK)

## Documentation Review

- [ ] Read KG_SUMMARY.md
- [ ] Read KG_QUICK_START.md
- [ ] Understand Architecture.md (optional)
- [ ] Bookmark guides for future reference

## Troubleshooting

If any test fails:

1. **Neo4j Connection Error**
   - [ ] Check Neo4j is running
   - [ ] Check credentials in .env
   - [ ] Verify URI format

2. **Module Import Error**
   - [ ] Verify neo4j_kg.py in backend/
   - [ ] Verify kg_builder.py in backend/
   - [ ] Check dependencies installed

3. **PDF Upload Fails**
   - [ ] Check file is valid PDF
   - [ ] Check disk space available
   - [ ] Check file permissions

4. **Chat Returns No Answer**
   - [ ] Upload paper first
   - [ ] Check /kg-papers for paper
   - [ ] Try simpler questions
   - [ ] Check Neo4j status

## Success Criteria

You're done when:

✅ Neo4j is running and accessible
✅ All 2 new Python files in backend/
✅ main.py is updated or replaced
✅ Dependencies installed (neo4j, python-dotenv)
✅ .env has Neo4j credentials
✅ Backend starts with KG system initialized
✅ /health shows kg_ready: true
✅ /kg-status shows enabled: true, connected: true
✅ /papers endpoint works (existing feature)
✅ /upload-pdf builds KG and returns stats
✅ /kg-papers shows uploaded papers
✅ /chat queries use knowledge graph first
✅ Response includes context_source and kg_used
✅ System falls back to RAG when needed
✅ All existing features still work
✅ No breaking changes

## Time Estimate

Total time for complete setup: **30-60 minutes**
- Phase 1 (Neo4j): 10-15 min
- Phase 2-4 (Files & Config): 20 min
- Phase 5-12 (Testing): 10-30 min

**Congratulations! You now have knowledge graph functionality fully integrated!** 🎉