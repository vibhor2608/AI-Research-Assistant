# Knowledge Graph Quick Start Guide

## What is This?

The Knowledge Graph (KG) feature converts research papers into structured semantic representations stored in Neo4j. It enables intelligent question answering by understanding the relationships between concepts in papers.

**Example**: Instead of just keyword matching, the system understands that "BERT uses Transformers" and "Transformers improve on RNNs" - so it can answer "What does BERT use?" correctly.

## 5-Minute Setup

### 1. Install Neo4j (2 minutes)

**Option A: Using Docker (Easiest)**
```bash
docker run --name neo4j -d -p 7687:7687 -p 7474:7474 \
  -e NEO4J_AUTH=neo4j/password123 \
  neo4j:latest
```

**Option B: Download & Install**
- Go to https://neo4j.com/download/
- Install and run the server
- Default: `bolt://localhost:7687`, user `neo4j`

**Option C: Use Neo4j Cloud (Free)**
- https://neo4j.com/cloud/aura/ - Create free cloud database
- Copy the connection string

### 2. Update Your Backend (2 minutes)

In `backend/.env`:
```env
GROQ_API_KEY=your_groq_key_here

# Add these 3 lines:
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password123
```

### 3. Copy Files (1 minute)

Copy these files to your `backend/` folder:
- `neo4j_kg.py`
- `kg_builder.py`

Then either:
- Replace `main.py` with `main_with_kg.py`, OR
- Manually merge changes (see Integration Guide)

### 4. Install Dependencies (1 minute)

```bash
cd backend
pip install neo4j==5.14.0 python-dotenv==1.0.0
```

### 5. Restart Backend

```bash
cd backend
uvicorn main:app --reload
```

## Usage

### Upload a Paper

In the web UI:
1. Click **Upload PDF** tab
2. Drag-and-drop a research paper PDF
3. Wait for processing (~20-30 seconds)
4. See the graph stats:
   ```
   ✓ Knowledge graph created: 24 entities, 18 relationships
   ```

### Ask Questions

In the **Deep Chat** tab:
1. Type a question: "What methods does this paper use?"
2. The system will answer by querying the knowledge graph
3. Look for `context_source: "Knowledge Graph"` in response

### Check What's in the Graph

```bash
# View all papers with knowledge graphs
curl http://localhost:8000/kg-papers

# View a specific paper's graph
curl http://localhost:8000/kg-paper/your_paper_name

# Check system status
curl http://localhost:8000/kg-status
```

## What Gets Extracted?

### Entities (24 per paper on average)
- **CONCEPT**: Transformers, RNNs, BERT
- **ALGORITHM**: Attention mechanism, backpropagation
- **DATASET**: ImageNet, MNIST, SQuAD
- **METHOD**: Fine-tuning, pre-training
- **METRIC**: BLEU score, F1 score
- **TOOL**: PyTorch, TensorFlow
- **AUTHOR**: Authors of the paper
- **RESULT**: Accuracy gains, improvements

### Relationships (15-20 per paper)
- `USES` - BERT uses Transformers
- `IMPROVES` - This work improves on X
- `IMPLEMENTS` - We implement algorithm Y
- `APPLIES_TO` - This method applies to NLP
- `EXTENDS` - Extends previous work
- `BASED_ON` - Based on algorithm Z

## Example Workflow

### Step 1: Upload Paper
```
File: attention_is_all_you_need.pdf
↓
Status: Extracting entities... (10s)
Status: Extracting relationships... (15s)
Status: Creating Neo4j graph... (5s)
✓ Knowledge graph created: 32 entities, 25 relationships
```

### Step 2: Ask Questions
```
Q: "What is the main architecture used?"
A: "The paper introduces the Transformer architecture. It uses self-attention mechanisms to process sequences in parallel, unlike RNNs which process sequentially."
[context_source: "Knowledge Graph"]

Q: "How does it improve on previous methods?"
A: "The Transformer improves on RNNs and LSTMs by allowing parallel processing through self-attention, reducing training time while improving translation quality."
[context_source: "Knowledge Graph"]

Q: "What datasets were used for evaluation?"
A: "The paper evaluates on the WMT 2014 English-German translation task and the WMT 2014 English-French translation task."
[context_source: "Knowledge Graph"]
```

### Step 3: Upload Another Paper
```
File: bert_paper.pdf
↓
✓ Knowledge graph created: 28 entities, 22 relationships
↓
Chat now uses BERT paper's graph
```

## Smart Fallback System

The system has intelligent fallbacks:

```
User asks question
  ↓
  Try: Knowledge Graph
    ✓ Found answer → Return KG answer
    ✗ No match → Continue
  ↓
  Try: FAISS RAG (existing semantic search)
    ✓ Found chunks → Return RAG answer
    ✗ No chunks → Continue
  ↓
  Try: Paper abstract (if available)
    ✓ Has abstract → Return abstract answer
    ✗ No abstract → Error
```

So even if the KG can't answer, RAG will try. No loss of functionality!

## API Reference

### Check System Status
```bash
curl http://localhost:8000/kg-status
```

Response:
```json
{
  "enabled": true,
  "connected": true,
  "papers": [
    {
      "paper_id": "attention_is_all_you_need",
      "filename": "attention_is_all_you_need.pdf",
      "entity_count": 32
    }
  ],
  "current_paper": "attention_is_all_you_need",
  "paper_count": 1
}
```

### List All Papers
```bash
curl http://localhost:8000/kg-papers
```

### Get Paper Details
```bash
curl http://localhost:8000/kg-paper/paper_name
```

Response:
```json
{
  "paper_id": "paper_name",
  "entity_count": 28,
  "relationship_count": 22
}
```

### Delete a Paper's Graph
```bash
curl -X DELETE http://localhost:8000/kg-paper/paper_name
```

### Chat (with KG support)
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What methods does this paper use?"}'
```

Response includes:
```json
{
  "answer": "...",
  "context_source": "Knowledge Graph",  // or "PDF (RAG)" or "Abstract"
  "kg_used": true  // Shows if KG was used
}
```

## Troubleshooting

### Q: "Knowledge graph not available"
**A:** Neo4j isn't running. Start it:
```bash
# Docker
docker start neo4j

# Or locally: Launch Neo4j application
```

### Q: "No entities extracted"
**A:** Paper text unclear. System falls back to RAG automatically. ✓ Works fine!

### Q: "Graph query returned nothing"
**A:** Question doesn't match graph entities. System uses RAG instead. ✓ Works fine!

### Q: How do I delete a paper?
**A:** Use DELETE endpoint:
```bash
curl -X DELETE http://localhost:8000/kg-paper/paper_name
```

### Q: Can I use multiple papers at once?
**A:** Currently, RAG is single-paper. KG supports listing all papers via `/kg-papers`. Future version will query multiple graphs.

## Performance Tips

- **Paper too large?** System processes first 8000 characters. That's usually enough.
- **Slow extraction?** Takes 20-40 seconds. This is the LLM time. Normal.
- **Better results?** Longer, clearer papers extract better entities.

## What's Different From Before?

| Feature | Before | Now |
|---------|--------|-----|
| Paper upload | ✓ Builds RAG index | ✓ RAG + Knowledge Graph |
| Chat answer source | Only semantic search | KG → RAG → Abstract |
| Multiple papers | Only last paper | All papers in Neo4j |
| Question answering | Chunk similarity | Semantic understanding |
| Relationship understanding | No | Yes! Understands how concepts relate |

## Next Steps

1. **Try it out** - Upload a paper and ask questions!
2. **Monitor** - Check `/kg-status` to see what's in the graph
3. **Experiment** - Try different question types
4. **Feedback** - Note what works well and what doesn't

## Advanced: Manual Graph Query

If Neo4j is running, visit:
```
http://localhost:7474
```

Then run Cypher queries:
```cypher
// See all papers
MATCH (p:Paper) RETURN p

// See entities in a paper
MATCH (p:Paper {paper_id: "your_paper"})<-[:IN_PAPER]-(e:Entity) RETURN e

// See relationships
MATCH (e1:Entity)-[r:RELATED]->(e2:Entity) RETURN e1, r, e2 LIMIT 10
```

## Questions?

Check the full guide: `KNOWLEDGE_GRAPH_INTEGRATION.md`

Enjoy intelligent paper analysis! 🚀