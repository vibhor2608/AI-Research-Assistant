"""
Knowledge Graph Builder
Converts paper text into structured knowledge graphs
"""

import json
import logging
from typing import List, Dict, Optional, Tuple
from groq import Groq
import re

logger = logging.getLogger(__name__)


class KnowledgeGraphBuilder:
    """Builds knowledge graphs from research paper text."""
    
    def __init__(self, groq_client: Groq):
        """Initialize with Groq client."""
        self.groq_client = groq_client
    
    def extract_entities(self, text: str, title: str = None) -> List[Dict]:
        """
        Extract key entities from paper text.
        
        Args:
            text: Paper text content
            title: Paper title for context
        
        Returns:
            List of entities: [{"id", "name", "type", "description"}, ...]
        """
        # Truncate text for LLM processing
        max_chars = 8000
        if len(text) > max_chars:
            text = text[:max_chars] + "...[truncated]"
        
        title_context = f'Paper: "{title}"\n\n' if title else ""
        
        prompt = f"""You are an expert at extracting structured knowledge from research papers.
Analyze this research paper and extract ALL important entities.

{title_context}Paper Text:
{text}

IMPORTANT: Respond ONLY with valid JSON. No other text.

Extract entities and return ONLY this JSON structure:
{{
  "entities": [
    {{
      "id": "unique_id",
      "name": "Entity Name",
      "type": "CONCEPT|METHOD|ALGORITHM|DATASET|METRIC|AUTHOR|TOOL|RESULT",
      "description": "Brief description of what this entity is"
    }}
  ]
}}

Guidelines:
- Extract 15-30 most important entities
- Types: CONCEPT (abstract ideas), METHOD (approaches/techniques), ALGORITHM (specific algorithms),
  DATASET (data used), METRIC (evaluation metrics), AUTHOR (person names), TOOL (software/libraries), RESULT (outcomes)
- Descriptions should be 1-2 sentences max
- IDs should be lowercase with underscores (e.g., "neural_networks", "bert_model")
"""

        try:
            response = self.groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000,
            )
            
            raw = response.choices[0].message.content.strip()
            
            # Clean JSON if needed
            raw = re.sub(r"```json\s*", "", raw)
            raw = re.sub(r"```\s*", "", raw)
            
            result = json.loads(raw)
            entities = result.get("entities", [])
            
            logger.info(f"✓ Extracted {len(entities)} entities from paper")
            return entities
        
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing entities JSON: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Error extracting entities: {str(e)}")
            return []
    
    def extract_relationships(self, text: str, entities: List[Dict], 
                             title: str = None) -> List[Dict]:
        """
        Extract relationships between entities.
        
        Args:
            text: Paper text content
            entities: List of extracted entities
            title: Paper title
        
        Returns:
            List of relationships: [{"source", "target", "type", "description"}, ...]
        """
        # Truncate text for LLM processing
        max_chars = 10000
        if len(text) > max_chars:
            text = text[:max_chars] + "...[truncated]"
        
        # Create entity context
        entity_list = "\n".join([
            f"- {e['id']}: {e['name']} ({e['type']})"
            for e in entities[:30]
        ])
        
        title_context = f'Paper: "{title}"\n\n' if title else ""
        
        prompt = f"""You are an expert at extracting relationships from research papers.
Given the entities and paper text, identify how entities relate to each other.

{title_context}Entities:
{entity_list}

Paper Text:
{text}

IMPORTANT: Respond ONLY with valid JSON. No other text.

Extract relationships and return ONLY this JSON structure:
{{
  "relationships": [
    {{
      "source": "entity_id_1",
      "target": "entity_id_2",
      "type": "USES|IMPROVES|IMPLEMENTS|COMPARES_WITH|RELATES_TO|BASED_ON|EXTENDS|APPLIES_TO",
      "description": "How source relates to target"
    }}
  ]
}}

Guidelines:
- Only use entity IDs from the provided entity list
- Types: USES (entity A uses entity B), IMPROVES (A improves on B), IMPLEMENTS (A implements B),
  COMPARES_WITH (A compared with B), RELATES_TO (general relationship), BASED_ON (A builds on B),
  EXTENDS (A extends B), APPLIES_TO (A applies to B)
- Extract 10-25 most important relationships
- Descriptions should be 1-2 sentences max
- Each relationship should be meaningful and supported by the text
"""

        try:
            response = self.groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000,
            )
            
            raw = response.choices[0].message.content.strip()
            
            # Clean JSON if needed
            raw = re.sub(r"```json\s*", "", raw)
            raw = re.sub(r"```\s*", "", raw)
            
            result = json.loads(raw)
            relationships = result.get("relationships", [])
            
            # Filter relationships to only valid entity IDs
            valid_entity_ids = {e['id'] for e in entities}
            relationships = [
                r for r in relationships
                if r.get('source') in valid_entity_ids and r.get('target') in valid_entity_ids
            ]
            
            logger.info(f"✓ Extracted {len(relationships)} relationships from paper")
            return relationships
        
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing relationships JSON: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Error extracting relationships: {str(e)}")
            return []
    
    def build_knowledge_graph(self, paper_text: str, paper_id: str, 
                             title: str = None) -> Tuple[List[Dict], List[Dict]]:
        """
        Build complete knowledge graph from paper.
        
        Args:
            paper_text: Full paper text
            paper_id: Unique ID for the paper
            title: Paper title
        
        Returns:
            Tuple of (entities, relationships)
        """
        logger.info(f"Building knowledge graph for paper {paper_id}")
        
        # Extract entities
        entities = self.extract_entities(paper_text, title)
        
        if not entities:
            logger.warning(f"No entities extracted for paper {paper_id}")
            return [], []
        
        # Extract relationships
        relationships = self.extract_relationships(paper_text, entities, title)
        
        logger.info(f"Knowledge graph built: {len(entities)} entities, {len(relationships)} relationships")
        
        return entities, relationships
    
    def extract_entities_for_query(self, question: str) -> List[str]:
        """
        Extract key entities/keywords from user question.
        
        Args:
            question: User's question
        
        Returns:
            List of entity names to search for
        """
        prompt = f"""Given this research question, extract key entity names and concepts to search for.

Question: {question}

IMPORTANT: Respond ONLY with valid JSON. No other text.

{{
  "entities": ["entity1", "entity2", "entity3"]
}}

Extract 2-5 key entities/concepts from the question."""

        try:
            response = self.groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=300,
            )
            
            raw = response.choices[0].message.content.strip()
            raw = re.sub(r"```json\s*", "", raw)
            raw = re.sub(r"```\s*", "", raw)
            
            result = json.loads(raw)
            return result.get("entities", [])
        
        except Exception as e:
            logger.error(f"Error extracting query entities: {str(e)}")
            # Fallback: extract words from question
            return [word for word in question.split() if len(word) > 3]