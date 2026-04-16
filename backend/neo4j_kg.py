def wipe_all(self) -> bool:
        """Delete all nodes and relationships in the database."""
        if not self.is_connected():
            return False
        try:
            with self.driver.session() as session:
                session.run("MATCH (n) DETACH DELETE n")
            logger.info("✓ Wiped all nodes and relationships from Neo4j")
            return True
        except Exception as e:
            logger.error(f"Error wiping all nodes: {str(e)}")
            return False
"""
Neo4j Knowledge Graph Manager
Handles knowledge graph operations for research papers
"""

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError
import os
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class KnowledgeGraphManager:
    """Manages Neo4j knowledge graph operations."""
    
    def __init__(self, uri: str = None, user: str = None, password: str = None):
        """Initialize Neo4j connection."""
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "password")
        self.driver = None
        self._connected = False
        
    def connect(self) -> bool:
        """Establish connection to Neo4j."""
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            self._connected = True
            logger.info("✓ Connected to Neo4j")
            return True
        except (ServiceUnavailable, AuthError) as e:
            logger.warning(f"⚠ Neo4j connection failed: {str(e)}")
            logger.warning("  Knowledge graph features will be disabled. Ensure Neo4j is running.")
            self._connected = False
            return False
    
    def is_connected(self) -> bool:
        """Check if connected to Neo4j."""
        return self._connected and self.driver is not None
    
    def close(self):
        """Close Neo4j connection."""
        if self.driver:
            self.driver.close()
            self._connected = False
    
    def create_paper_graph(self, paper_id: str, filename: str, entities: List[Dict], 
                          relationships: List[Dict]) -> bool:
        """
        Create a knowledge graph for a paper.
        
        Args:
            paper_id: Unique identifier for the paper
            filename: Name of the PDF file
            entities: List of {"id", "name", "type", "description"} dicts
            relationships: List of {"source", "target", "type", "description"} dicts
        
        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected():
            return False
        
        try:
            with self.driver.session() as session:
                # Create paper node
                session.run("""
                    MERGE (p:Paper {paper_id: $paper_id})
                    SET p.filename = $filename,
                        p.created_at = datetime(),
                        p.updated_at = datetime()
                """, paper_id=paper_id, filename=filename)
                
                # Create entity nodes
                for entity in entities:
                    session.run("""
                        MERGE (e:Entity {entity_id: $entity_id, paper_id: $paper_id})
                        SET e.name = $name,
                            e.type = $type,
                            e.description = $description
                        WITH e, $paper_id as pid
                        MATCH (p:Paper {paper_id: pid})
                        MERGE (e)-[:IN_PAPER]->(p)
                    """, 
                    entity_id=f"{paper_id}_{entity['id']}",
                    paper_id=paper_id,
                    name=entity.get('name', ''),
                    type=entity.get('type', ''),
                    description=entity.get('description', '')
                    )
                
                # Create relationships
                for rel in relationships:
                    session.run("""
                        MATCH (e1:Entity {entity_id: $source_id})
                        MATCH (e2:Entity {entity_id: $target_id})
                        MERGE (e1)-[r:RELATED {rel_type: $rel_type}]->(e2)
                        SET r.description = $description
                    """,
                    source_id=f"{paper_id}_{rel['source']}",
                    target_id=f"{paper_id}_{rel['target']}",
                    rel_type=rel.get('type', 'RELATES_TO'),
                    description=rel.get('description', '')
                    )
            
            logger.info(f"✓ Knowledge graph created for paper {paper_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error creating knowledge graph: {str(e)}")
            return False
    
    def query_graph(self, paper_id: str, question: str, top_k: int = 5) -> Dict:
        """
        Query the knowledge graph for relevant information.
        
        Args:
            paper_id: Paper to query
            question: Natural language question
            top_k: Number of relevant entities/relationships to return
        
        Returns:
            Dictionary with relevant entities, relationships, and context
        """
        if not self.is_connected():
            return {"entities": [], "relationships": [], "success": False}
        
        try:
            with self.driver.session() as session:
                # Find related entities and their relationships
                result = session.run("""
                    MATCH (p:Paper {paper_id: $paper_id})<-[:IN_PAPER]-(e:Entity)
                    OPTIONAL MATCH (e)-[r:RELATED]-(related:Entity)
                    RETURN {
                        entity: e,
                        relationships: collect({
                            type: type(r),
                            target: related.name,
                            description: r.description
                        })
                    } as graph_data
                    LIMIT $limit
                """, paper_id=paper_id, limit=top_k)
                
                entities = []
                relationships = []
                
                for record in result:
                    data = record["graph_data"]
                    if data:
                        entity_props = dict(data["entity"])
                        entities.append(entity_props)
                        
                        if data["relationships"]:
                            relationships.extend(data["relationships"])
                
                return {
                    "entities": entities,
                    "relationships": relationships,
                    "success": True
                }
        
        except Exception as e:
            logger.error(f"Error querying knowledge graph: {str(e)}")
            return {"entities": [], "relationships": [], "success": False}
    
    def get_paper_summary(self, paper_id: str) -> Dict:
        """Get summary of knowledge graph for a paper."""
        if not self.is_connected():
            return {"paper_id": paper_id, "entity_count": 0, "relationship_count": 0}
        
        try:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (p:Paper {paper_id: $paper_id})
                    OPTIONAL MATCH (p)<-[:IN_PAPER]-(e:Entity)
                    OPTIONAL MATCH (e)-[r:RELATED]-()
                    RETURN 
                        count(DISTINCT e) as entity_count,
                        count(DISTINCT r) as relationship_count
                """, paper_id=paper_id)
                
                record = result.single()
                return {
                    "paper_id": paper_id,
                    "entity_count": record["entity_count"] if record else 0,
                    "relationship_count": record["relationship_count"] if record else 0
                }
        
        except Exception as e:
            logger.error(f"Error getting graph summary: {str(e)}")
            return {"paper_id": paper_id, "entity_count": 0, "relationship_count": 0}
    
    def list_papers(self) -> List[Dict]:
        """List all papers with their knowledge graphs."""
        if not self.is_connected():
            return []
        
        try:
            with self.driver.session() as session:
                result = session.run("""
                    MATCH (p:Paper)
                    OPTIONAL MATCH (p)<-[:IN_PAPER]-(e:Entity)
                    RETURN p.paper_id as paper_id, p.filename as filename,
                           count(DISTINCT e) as entity_count
                """)
                
                papers = []
                for record in result:
                    papers.append({
                        "paper_id": record["paper_id"],
                        "filename": record["filename"],
                        "entity_count": record["entity_count"]
                    })
                
                return papers
        
        except Exception as e:
            logger.error(f"Error listing papers: {str(e)}")
            return []
    
    def delete_paper_graph(self, paper_id: str) -> bool:
        """Delete a paper and its knowledge graph."""
        if not self.is_connected():
            return False
        
        try:
            with self.driver.session() as session:
                session.run("""
                    MATCH (p:Paper {paper_id: $paper_id})
                    DETACH DELETE p
                """, paper_id=paper_id)
            
            logger.info(f"✓ Deleted knowledge graph for paper {paper_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error deleting knowledge graph: {str(e)}")
            return False
    
    def get_graph_context(self, paper_id: str, entity_names: List[str]) -> str:
        """
        Get context from knowledge graph for specific entities.
        
        Args:
            paper_id: Paper to query
            entity_names: Names of entities to get context for
        
        Returns:
            Formatted context string
        """
        if not self.is_connected():
            return ""
        
        try:
            with self.driver.session() as session:
                context_parts = []
                
                for entity_name in entity_names:
                    result = session.run("""
                        MATCH (e:Entity {paper_id: $paper_id})
                        WHERE e.name CONTAINS $name
                        OPTIONAL MATCH (e)-[r:RELATED]-(related:Entity)
                        RETURN e.name as name, e.type as type, e.description as desc,
                               collect({name: related.name, type: type(r)}) as relationships
                    """, paper_id=paper_id, name=entity_name)
                    
                    for record in result:
                        context_parts.append(
                            f"{record['name']} ({record['type']}): {record['desc']}"
                        )
                        if record['relationships']:
                            for rel in record['relationships']:
                                context_parts.append(
                                    f"  - {rel['type']} {rel['name']}"
                                )
                
                return "\n".join(context_parts)
        
        except Exception as e:
            logger.error(f"Error getting graph context: {str(e)}")
            return ""


# Global instance
kg_manager = None


def init_knowledge_graph_manager() -> KnowledgeGraphManager:
    """Initialize and connect knowledge graph manager."""
    global kg_manager
    kg_manager = KnowledgeGraphManager()
    kg_manager.connect()
    return kg_manager


def get_kg_manager() -> Optional[KnowledgeGraphManager]:
    """Get the knowledge graph manager instance."""
    return kg_manager