"""
Knowledge Graph Agent - Query WikiGR using natural language.

Simple library approach: direct Kuzu access + Claude for synthesis.
No MCP server, no daemon, just a Python class.
"""

import json
import logging
import re
from typing import Any

import kuzu
from anthropic import Anthropic

logger = logging.getLogger(__name__)


class KnowledgeGraphAgent:
    """Agent that queries WikiGR knowledge graph and synthesizes answers."""

    def __init__(self, db_path: str, anthropic_api_key: str | None = None, read_only: bool = True):
        """
        Initialize agent with database connection and Claude API.

        Args:
            db_path: Path to WikiGR Kuzu database
            anthropic_api_key: Anthropic API key (or from ANTHROPIC_API_KEY env var)
            read_only: Open database in read-only mode (allows concurrent access during expansion)
        """
        self.db = kuzu.Database(db_path, read_only=read_only)
        self.conn = kuzu.Connection(self.db)
        self.claude = Anthropic(api_key=anthropic_api_key)

        logger.info(f"KnowledgeGraphAgent initialized with db: {db_path} (read_only={read_only})")

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
        kg_results = self._execute_query(
            query_plan["cypher"], max_results, query_plan.get("cypher_params")
        )

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

You MUST return ONLY valid JSON in this exact format (no extra text):
{{
  "type": "entity_search",
  "cypher": "MATCH ... RETURN ...",
  "explanation": "Why this query"
}}

Generate efficient Cypher with LIMIT 10. Return ONLY the JSON, nothing else."""

        try:
            response = self.claude.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:
            logger.warning(f"Claude API error in _plan_query: {e}")
            return {
                "type": "entity_search",
                "cypher": "MATCH (a:Article) WHERE lower(a.title) CONTAINS lower($q) RETURN a.title AS title LIMIT 10",
                "cypher_params": {"q": question},
                "explanation": f"Fallback query due to API error: {type(e).__name__}",
            }

        if not response.content:
            logger.warning("Empty response from Claude in _plan_query")
            return {
                "type": "entity_search",
                "cypher": "MATCH (a:Article) WHERE lower(a.title) CONTAINS lower($q) RETURN a.title AS title LIMIT 10",
                "cypher_params": {"q": question},
                "explanation": "Fallback query due to empty response",
            }

        content = response.content[0].text
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse failed: {e}. Response: {content[:200]}")
            # Fallback: simple entity search using parameterized query
            return {
                "type": "entity_search",
                "cypher": "MATCH (a:Article) WHERE lower(a.title) CONTAINS lower($q) RETURN a.title AS title LIMIT 10",
                "cypher_params": {"q": question},
                "explanation": "Fallback query due to JSON parse error",
            }

    @staticmethod
    def _validate_cypher(cypher: str) -> None:
        """Reject Cypher queries containing write operations.

        Raises ValueError if the query contains destructive keywords.
        """
        # Normalize whitespace for matching
        normalized = re.sub(r"\s+", " ", cypher.upper())
        write_keywords = [
            "CREATE ",
            "DELETE ",
            "DETACH ",
            "DROP ",
            "SET ",
            "MERGE ",
            "REMOVE ",
        ]
        for keyword in write_keywords:
            if keyword in normalized:
                raise ValueError(f"Write operation rejected: query contains {keyword.strip()}")

    def _execute_query(self, cypher: str, limit: int, params: dict | None = None) -> dict:
        """Execute Cypher query and structure results."""
        try:
            self._validate_cypher(cypher)
            result = self.conn.execute(cypher, params or {})
            df = result.get_as_df()

            if df.empty:
                return {"sources": [], "entities": [], "facts": [], "raw": []}

            # Structure results based on columns
            raw_records = df.to_dict(orient="records")[:limit]
            structured = {
                "sources": [],
                "entities": [],
                "facts": [],
                "raw": raw_records,
            }

            # Extract sources (article titles) - handle both columns and nested node objects
            for record in raw_records:
                # Check for direct title column
                for key, value in record.items():
                    if "title" in key.lower() and isinstance(value, str):
                        structured["sources"].append(value)
                    # Check for nested Article node
                    elif isinstance(value, dict) and value.get("_label") == "Article":
                        title = value.get("title")
                        if title:
                            structured["sources"].append(title)

            structured["sources"] = list(set(structured["sources"]))[:limit]  # Dedupe

            # Extract entities - handle both "name" and "e.name" column names
            name_cols = [c for c in df.columns if "name" in c.lower()]
            if name_cols:
                for _, row in df.iterrows():
                    name = row.get(name_cols[0])
                    if name:
                        # Try to get type from any column with "type" in name
                        type_cols = [c for c in df.columns if "type" in c.lower()]
                        entity_type = row.get(type_cols[0], "unknown") if type_cols else "unknown"
                        structured["entities"].append({"name": name, "type": entity_type})

            # Extract facts
            if "content" in df.columns:
                structured["facts"] = df["content"].dropna().tolist()[:limit]

            return structured

        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            return {"sources": [], "entities": [], "facts": [], "error": str(e)}

    def _synthesize_answer(self, question: str, kg_results: dict, query_plan: dict) -> str:
        """Use Claude to synthesize natural language answer from KG results."""
        # Handle error case
        if "error" in kg_results:
            return f"Query execution failed: {kg_results['error']}"

        # Prepare context from KG
        context = f"""Query Type: {query_plan["type"]}
Cypher: {query_plan["cypher"]}

Sources: {", ".join(kg_results.get("sources", [])[:5])}

Entities found: {json.dumps(kg_results.get("entities", [])[:10], indent=2)}

Facts:
{chr(10).join(f"- {fact}" for fact in kg_results.get("facts", [])[:10])}

Raw results: {json.dumps(kg_results.get("raw", [])[:5], indent=2, default=str)}
"""

        prompt = f"""Using the knowledge graph query results below, answer this question concisely.

Question: {question}

Knowledge Graph Results:
{context}

Provide a clear, factual answer citing the sources. If the KG has no relevant data, say so."""

        try:
            response = self.claude.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:
            logger.warning(f"Claude API error in _synthesize_answer: {e}")
            sources = ", ".join(kg_results.get("sources", [])[:5])
            return f"Found relevant sources: {sources}" if sources else "No results found."

        if not response.content:
            return "Unable to synthesize answer: empty response from Claude."

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
            "properties": (
                json.loads(row["properties"])
                if isinstance(row["properties"], str)
                else row["properties"] or {}
            ),
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
        if not isinstance(max_hops, int) or not (1 <= max_hops <= 10):
            raise ValueError(f"max_hops must be an integer between 1 and 10, got {max_hops!r}")

        # Simplified query without path list comprehensions (Kuzu limitation)
        result = self.conn.execute(
            f"""
            MATCH path = (src:Entity {{name: $src}})-[:ENTITY_RELATION*1..{max_hops}]->(tgt:Entity {{name: $tgt}})
            RETURN src.name AS source, tgt.name AS target, length(path) AS hops
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
                {
                    "source": row["source"],
                    "target": row["target"],
                    "hops": row["hops"],
                    "note": "Full path details require multiple queries in Kuzu",
                }
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
            query: Search query (must be an existing article title)
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

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        """Close database connection."""
        self.conn = None  # type: ignore[assignment]
        self.db = None  # type: ignore[assignment]
