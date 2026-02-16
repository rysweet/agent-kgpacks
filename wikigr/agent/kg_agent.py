"""
Knowledge Graph Agent - Query WikiGR using natural language.

Simple library approach: direct Kuzu access + Claude for synthesis.
No MCP server, no daemon, just a Python class.
"""

import json
import logging
from typing import Any

import kuzu
from anthropic import Anthropic

logger = logging.getLogger(__name__)


class KnowledgeGraphAgent:
    """Agent that queries WikiGR knowledge graph and synthesizes answers."""

    def __init__(self, db_path: str, anthropic_api_key: str | None = None):
        """
        Initialize agent with database connection and Claude API.

        Args:
            db_path: Path to WikiGR Kuzu database
            anthropic_api_key: Anthropic API key (or from ANTHROPIC_API_KEY env var)
        """
        self.db = kuzu.Database(db_path)
        self.conn = kuzu.Connection(self.db)
        self.claude = Anthropic(api_key=anthropic_api_key)

        logger.info(f"KnowledgeGraphAgent initialized with db: {db_path}")

    def query(self, question: str, max_results: int = 10) -> dict[str, Any]:
        """
        Answer a question using the knowledge graph.

        Args:
            question: Natural language question
            max_results: Maximum number of results to retrieve from graph

        Returns:
            {
                "answer": "Natural language answer",
                "sources": ["Article 1", "Article 2"],
                "entities": [{"name": "...", "type": "..."}],
                "facts": ["Fact 1", "Fact 2"],
                "cypher_query": "MATCH ... (for transparency)"
            }
        """
        # Step 1: Classify query type and generate Cypher
        query_plan = self._plan_query(question)

        # Step 2: Execute Cypher query
        kg_results = self._execute_query(query_plan["cypher"], max_results)

        # Step 3: Synthesize answer with Claude
        answer = self._synthesize_answer(question, kg_results, query_plan)

        return {
            "answer": answer,
            "sources": kg_results.get("sources", []),
            "entities": kg_results.get("entities", []),
            "facts": kg_results.get("facts", []),
            "cypher_query": query_plan["cypher"],
            "query_type": query_plan["type"],
        }

    def _plan_query(self, question: str) -> dict:
        """Use Claude to classify question and generate Cypher query."""
        prompt = f"""You are a Cypher query generator for a Wikipedia knowledge graph.

The graph schema:
- Article (title, category, word_count)
- Entity (name, type, properties) - extracted entities like people, places, concepts
- Fact (content, source_article) - key facts
- Section (content, embedding) - article sections with semantic embeddings
- Relationships: HAS_ENTITY, HAS_FACT, ENTITY_RELATION, LINKS_TO, HAS_SECTION

Question: {question}

Classify the question type and generate a Cypher query:

1. **entity_search**: "Who is X?" or "What is Y?"
   → Find Entity or Article by name

2. **relationship_path**: "How is X related to Y?"
   → Find path between two entities via ENTITY_RELATION edges

3. **fact_retrieval**: "What are facts about X?"
   → Find Article → HAS_FACT → Fact

4. **semantic_search**: "Articles similar to X"
   → Use vector search on Section embeddings

5. **entity_relationships**: "What did X do?" or "Who founded Y?"
   → Find Entity → ENTITY_RELATION (with specific relation type)

Return JSON:
{{
  "type": "entity_search|relationship_path|fact_retrieval|semantic_search|entity_relationships",
  "cypher": "MATCH ... RETURN ...",
  "explanation": "Why this query type"
}}

Generate efficient Cypher with LIMIT 10."""

        response = self.claude.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        content = response.content[0].text
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse failed: {e}. Response: {content[:200]}")
            # Fallback: simple entity search
            safe_question = question.replace("'", "")
            return {
                "type": "entity_search",
                "cypher": f"MATCH (a:Article) WHERE lower(a.title) CONTAINS lower('{safe_question}') RETURN a.title AS title LIMIT 10",
                "explanation": "Fallback query due to JSON parse error",
            }

    def _execute_query(self, cypher: str, limit: int) -> dict:
        """Execute Cypher query and structure results."""
        try:
            result = self.conn.execute(cypher)
            df = result.get_as_df()

            if df.empty:
                return {"sources": [], "entities": [], "facts": [], "raw": []}

            # Structure results based on columns
            structured = {
                "sources": [],
                "entities": [],
                "facts": [],
                "raw": df.to_dict(orient="records")[:limit],
            }

            # Extract sources (article titles)
            if "title" in df.columns:
                structured["sources"] = df["title"].dropna().unique().tolist()[:limit]

            # Extract entities
            if "name" in df.columns and "type" in df.columns:
                for _, row in df.iterrows():
                    if row.get("name"):
                        structured["entities"].append(
                            {"name": row["name"], "type": row.get("type", "unknown")}
                        )

            # Extract facts
            if "content" in df.columns:
                structured["facts"] = df["content"].dropna().tolist()[:limit]

            return structured

        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            return {"sources": [], "entities": [], "facts": [], "error": str(e)}

    def _synthesize_answer(self, question: str, kg_results: dict, query_plan: dict) -> str:
        """Use Claude to synthesize natural language answer from KG results."""
        # Prepare context from KG
        context = f"""Query Type: {query_plan["type"]}
Cypher: {query_plan["cypher"]}

Sources: {", ".join(kg_results["sources"][:5])}

Entities found: {json.dumps(kg_results["entities"][:10], indent=2)}

Facts:
{chr(10).join(f"- {fact}" for fact in kg_results["facts"][:10])}

Raw results: {json.dumps(kg_results["raw"][:5], indent=2)}
"""

        prompt = f"""Using the knowledge graph query results below, answer this question concisely.

Question: {question}

Knowledge Graph Results:
{context}

Provide a clear, factual answer citing the sources. If the KG has no relevant data, say so."""

        response = self.claude.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )

        return response.content[0].text

    def find_entity(self, entity_name: str) -> dict | None:
        """
        Find an entity by name.

        Args:
            entity_name: Entity name to search for

        Returns:
            Entity details with type, properties, and source articles
        """
        result = self.conn.execute(
            """
            MATCH (e:Entity {name: $name})
            OPTIONAL MATCH (a:Article)-[:HAS_ENTITY]->(e)
            RETURN e.name AS name, e.type AS type, e.properties AS properties,
                   collect(a.title) AS source_articles
            """,
            {"name": entity_name},
        )

        df = result.get_as_df()
        if df.empty:
            return None

        row = df.iloc[0]
        return {
            "name": row["name"],
            "type": row["type"],
            "properties": json.loads(row["properties"]) if row["properties"] else {},
            "source_articles": row["source_articles"],
        }

    def find_relationship_path(
        self, source_entity: str, target_entity: str, max_hops: int = 3
    ) -> list[dict]:
        """
        Find relationship paths between two entities.

        Args:
            source_entity: Source entity name
            target_entity: Target entity name
            max_hops: Maximum path length

        Returns:
            List of paths with relationships
        """
        result = self.conn.execute(
            f"""
            MATCH path = (src:Entity {{name: $src}})-[:ENTITY_RELATION*1..{max_hops}]->(tgt:Entity {{name: $tgt}})
            RETURN [rel in relationships(path) | rel.relation] AS relations,
                   [node in nodes(path) | node.name] AS entities,
                   length(path) AS hops
            ORDER BY hops ASC
            LIMIT 5
            """,
            {"src": source_entity, "tgt": target_entity},
        )

        df = result.get_as_df()
        if df.empty:
            return []

        paths = []
        for _, row in df.iterrows():
            paths.append(
                {"entities": row["entities"], "relations": row["relations"], "hops": row["hops"]}
            )

        return paths

    def get_entity_facts(self, entity_or_article: str) -> list[str]:
        """
        Get all facts about an entity or article.

        Args:
            entity_or_article: Entity name or article title

        Returns:
            List of fact strings
        """
        # Try as article first
        result = self.conn.execute(
            """
            MATCH (a:Article {title: $name})-[:HAS_FACT]->(f:Fact)
            RETURN f.content AS fact
            """,
            {"name": entity_or_article},
        )

        df = result.get_as_df()
        if not df.empty:
            return df["fact"].tolist()

        # Try as entity
        result = self.conn.execute(
            """
            MATCH (e:Entity {name: $name})<-[:HAS_ENTITY]-(a:Article)-[:HAS_FACT]->(f:Fact)
            RETURN DISTINCT f.content AS fact
            """,
            {"name": entity_or_article},
        )

        df = result.get_as_df()
        return df["fact"].tolist() if not df.empty else []

    def semantic_search(self, query: str, top_k: int = 10) -> list[dict]:
        """
        Semantic search over article sections.

        Args:
            query: Search query (can be an article title or free text)
            top_k: Number of results

        Returns:
            List of similar articles with similarity scores
        """
        # Get embedding for query (if it's an article title)
        result = self.conn.execute(
            """
            MATCH (a:Article {title: $query})-[:HAS_SECTION]->(s:Section)
            RETURN s.embedding AS embedding
            LIMIT 1
            """,
            {"query": query},
        )

        df = result.get_as_df()
        if df.empty:
            return []

        query_embedding = df.iloc[0]["embedding"]

        # Vector search
        result = self.conn.execute(
            """
            CALL QUERY_VECTOR_INDEX('Section', 'embedding_idx', $emb, $k)
            RETURN *
            """,
            {"emb": query_embedding, "k": top_k * 3},
        )

        df = result.get_as_df()
        if df.empty:
            return []

        # Aggregate by article
        articles = {}
        for _, row in df.iterrows():
            section_id = row["node"]["section_id"]
            article_title = section_id.split("#")[0]
            distance = row["distance"]

            if article_title not in articles or distance < articles[article_title]["distance"]:
                articles[article_title] = {
                    "title": article_title,
                    "similarity": 1.0 - distance,
                    "distance": distance,
                }

        # Sort by similarity
        results = sorted(articles.values(), key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    def close(self):
        """Close database connection."""
        del self.conn
        del self.db
