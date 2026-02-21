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


def _safe_json_loads(value: object) -> dict:
    """Parse JSON string to dict, returning {} on any failure."""
    if not isinstance(value, str):
        return value if isinstance(value, dict) else {}
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return {}


class KnowledgeGraphAgent:
    """Agent that queries WikiGR knowledge graph and synthesizes answers."""

    def __init__(
        self,
        db_path: str,
        anthropic_api_key: str | None = None,
        read_only: bool = True,
    ):
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
        self._embedding_generator = None

        logger.info(f"KnowledgeGraphAgent initialized with db: {db_path} (read_only={read_only})")

    def _check_open(self) -> None:
        """Raise RuntimeError if the agent has been closed."""
        if self.conn is None:
            raise RuntimeError("KnowledgeGraphAgent is closed. Create a new instance.")

    def _get_embedding_generator(self):
        """Lazily initialize and return the embedding generator.

        The sentence-transformers model is only loaded the first time this
        method is called, keeping startup fast when semantic search is not used.
        """
        if self._embedding_generator is None:
            from bootstrap.src.embeddings.generator import EmbeddingGenerator

            self._embedding_generator = EmbeddingGenerator()
        return self._embedding_generator

    def query(
        self,
        question: str,
        max_results: int = 10,
        use_graph_rag: bool = False,
    ) -> dict[str, Any]:
        """
        Answer a question using the knowledge graph.

        Args:
            question: Natural language question
            max_results: Maximum number of results to retrieve from graph (1-1000)
            use_graph_rag: If True, delegate to graph_query() for multi-hop
                retrieval that follows LINKS_TO edges before synthesizing.

        Returns:
            {
                "answer": "Natural language answer",
                "sources": ["Article 1", "Article 2"],
                "entities": [{"name": "...", "type": "..."}],
                "facts": ["Fact 1", "Fact 2"],
                "cypher_query": "MATCH ... (for transparency)"
            }
        """
        self._check_open()
        if use_graph_rag:
            return self.graph_query(question)
        if not isinstance(max_results, int) or not (1 <= max_results <= 1000):
            raise ValueError(
                f"max_results must be an integer between 1 and 1000, got {max_results!r}"
            )

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

    # ------------------------------------------------------------------
    # Graph-Aware RAG (multi-hop retrieval)
    # ------------------------------------------------------------------

    def graph_query(
        self,
        question: str,
        max_hops: int = 2,
        max_context_articles: int = 5,
    ) -> dict[str, Any]:
        """Answer using graph-aware multi-hop retrieval.

        Follows LINKS_TO edges from seed articles to gather context from
        related articles before synthesizing an answer.  This produces
        richer responses by exploiting the knowledge graph structure.

        Steps:
            1. Use Claude to identify seed entity/article names from the question.
            2. Traverse LINKS_TO edges up to *max_hops* to gather related articles.
            3. Collect the lead section content from each traversed article.
            4. Synthesize an answer using all gathered context.

        Args:
            question: Natural language question.
            max_hops: Maximum depth of LINKS_TO traversal (1-10).
            max_context_articles: Maximum number of related articles to
                collect per seed (1-50).

        Returns:
            Dictionary with keys: answer, sources, hops_traversed,
            articles_consulted, cypher_queries.
        """
        self._check_open()

        if not isinstance(max_hops, int) or not (1 <= max_hops <= 10):
            raise ValueError(f"max_hops must be an integer between 1 and 10, got {max_hops!r}")
        if not isinstance(max_context_articles, int) or not (1 <= max_context_articles <= 50):
            raise ValueError(
                f"max_context_articles must be an integer between 1 and 50, "
                f"got {max_context_articles!r}"
            )

        cypher_queries: list[str] = []

        # ------------------------------------------------------------------
        # Step 1: Ask Claude to extract seed article titles from the question
        # ------------------------------------------------------------------
        seed_titles = self._identify_seed_articles(question)
        logger.info(f"Graph RAG seeds identified: {seed_titles}")

        # ------------------------------------------------------------------
        # Step 2: Traverse LINKS_TO edges from each seed
        # ------------------------------------------------------------------
        all_related_titles: list[str] = []
        for seed_title in seed_titles:
            traversal_cypher = (
                f"MATCH (seed:Article)"
                f"-[:LINKS_TO*1..{max_hops}]->"
                f"(related:Article) "
                f"WHERE lower(seed.title) = lower($title) AND related.word_count > 0 "
                f"RETURN DISTINCT related.title AS title "
                f"LIMIT $limit"
            )
            cypher_queries.append(traversal_cypher)
            try:
                result = self.conn.execute(
                    traversal_cypher,
                    {"title": seed_title, "limit": max_context_articles},
                )
                df = result.get_as_df()
                if not df.empty:
                    all_related_titles.extend(df["title"].tolist())
            except Exception as e:
                logger.warning(f"Traversal failed for seed '{seed_title}': {e}")

        # Deduplicate while preserving order; include seeds themselves
        # Cap total articles to prevent excessive API costs
        max_total_articles = 15
        seen: set[str] = set()
        unique_titles: list[str] = []
        for title in seed_titles + all_related_titles:
            if title not in seen:
                seen.add(title)
                unique_titles.append(title)
            if len(unique_titles) >= max_total_articles:
                break

        # ------------------------------------------------------------------
        # Step 3: Gather lead-section content from each article
        # ------------------------------------------------------------------
        context_parts: list[str] = []
        section_cypher = (
            "MATCH (a:Article {title: $title})"
            "-[:HAS_SECTION {section_index: 0}]->(s:Section) "
            "RETURN s.content AS content"
        )
        cypher_queries.append(section_cypher)
        for title in unique_titles:
            try:
                result = self.conn.execute(section_cypher, {"title": title})
                df = result.get_as_df()
                if not df.empty:
                    content = df.iloc[0]["content"]
                    if content:
                        context_parts.append(f"## {title}\n{content}")
            except Exception as e:
                logger.warning(f"Section fetch failed for '{title}': {e}")

        # ------------------------------------------------------------------
        # Step 4: Synthesize the answer with Claude
        # ------------------------------------------------------------------
        combined_context = "\n\n".join(context_parts) if context_parts else "(no context found)"
        answer = self._synthesize_graph_rag_answer(question, combined_context, unique_titles)

        return {
            "answer": answer,
            "sources": unique_titles,
            "hops_traversed": max_hops,
            "articles_consulted": len(context_parts),
            "cypher_queries": cypher_queries,
        }

    def _identify_seed_articles(self, question: str) -> list[str]:
        """Use Claude to extract likely Wikipedia article titles from a question.

        Falls back to simple keyword extraction if the API call fails.
        """
        prompt = (
            "You are an assistant that identifies Wikipedia article titles "
            "relevant to a user question.  Given the question below, return a JSON list of "
            "1-3 Wikipedia article titles that are most likely to appear in a knowledge graph "
            "and would serve as good starting points for answering the question.\n\n"
            "Return ONLY a JSON array of strings, nothing else.\n"
            'Example: ["Machine Learning", "Neural Network"]\n\n'
            f"Question: {question}"
        )

        try:
            response = self.claude.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:
            logger.warning(f"Claude API error in _identify_seed_articles: {e}")
            return self._fallback_seed_extraction(question)

        if not response.content:
            return self._fallback_seed_extraction(question)

        text = response.content[0].text.strip()
        # Strip markdown fences if present
        if "```" in text:
            text = text.split("```")[1] if "```json" not in text else text.split("```json")[1]
            text = text.split("```")[0].strip()

        try:
            titles = json.loads(text)
            if isinstance(titles, list) and all(isinstance(t, str) for t in titles):
                return titles[:3]
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Failed to parse seed titles JSON: {text[:200]}")

        return self._fallback_seed_extraction(question)

    @staticmethod
    def _fallback_seed_extraction(question: str) -> list[str]:
        """Extract candidate article titles from question using simple heuristics.

        Capitalised multi-word phrases and known stop-word filtering provide a
        reasonable fallback when the LLM is unavailable.
        """
        stop_words = {
            "what",
            "who",
            "how",
            "why",
            "when",
            "where",
            "which",
            "does",
            "is",
            "are",
            "was",
            "were",
            "the",
            "a",
            "an",
            "of",
            "in",
            "on",
            "to",
            "for",
            "and",
            "or",
            "not",
            "can",
            "could",
            "would",
            "should",
            "do",
            "did",
            "has",
            "have",
            "had",
            "be",
            "been",
            "about",
            "between",
            "from",
            "with",
            "this",
            "that",
            "these",
            "those",
            "it",
            "its",
            "tell",
            "me",
            "us",
            "find",
            "explain",
            "describe",
            "relationship",
            "related",
            "knowledge",
            "graph",
            "article",
            "articles",
        }
        words = question.replace("?", "").replace("!", "").replace(",", "").split()
        candidates = [w for w in words if w.lower() not in stop_words and len(w) > 2]
        # Preserve original casing — case-insensitive matching happens in the traversal query
        return candidates[:3] if candidates else ["Artificial intelligence"]

    def _synthesize_graph_rag_answer(self, question: str, context: str, sources: list[str]) -> str:
        """Synthesize an answer from multi-hop graph context.

        Args:
            question: The original user question.
            context: Combined section content from traversed articles.
            sources: List of article titles used as context.

        Returns:
            Natural language answer string.
        """
        prompt = (
            "Using the following context gathered by traversing a Wikipedia "
            "knowledge graph, answer the question below.  Cite specific article titles "
            "where possible.\n\n"
            f"Question: {question}\n\n"
            f"Context from {len(sources)} articles:\n"
            f"{context}\n\n"
            "Provide a clear, factual answer. If the context is insufficient, say so."
        )

        try:
            response = self.claude.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:
            logger.warning(f"Claude API error in _synthesize_graph_rag_answer: {e}")
            return (
                f"Found {len(sources)} related articles: {', '.join(sources[:5])}"
                if sources
                else "No results found."
            )

        if not response.content:
            return "Unable to synthesize answer: empty response from Claude."

        return response.content[0].text

    # ------------------------------------------------------------------
    # Standard query helpers
    # ------------------------------------------------------------------

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
        """Reject Cypher queries containing write or DDL operations.

        Raises ValueError if the query contains destructive keywords
        or unbounded variable-length paths.
        """
        # Allowlist: only permit MATCH or CALL QUERY_VECTOR_INDEX
        # Strip string literals and comments to prevent bypass
        stripped = re.sub(r"'[^']*'", "''", cypher)
        stripped = re.sub(r'"[^"]*"', '""', stripped)
        stripped = re.sub(r"//.*$", "", stripped, flags=re.MULTILINE)
        stripped = re.sub(r"/\*.*?\*/", "", stripped, flags=re.DOTALL)
        normalized = re.sub(r"\s+", " ", stripped.upper()).strip()

        allowed_prefixes = ("MATCH ", "CALL QUERY_VECTOR_INDEX")
        if not any(normalized.startswith(p) for p in allowed_prefixes):
            raise ValueError("Query rejected: must start with MATCH or CALL QUERY_VECTOR_INDEX")

        # Blocklist for dangerous keywords (defense in depth)
        dangerous = [
            "CREATE ",
            "DELETE ",
            "DETACH ",
            "DROP ",
            "SET ",
            "MERGE ",
            "REMOVE ",
            "LOAD ",
            "COPY ",
            "ALTER ",
            "INSTALL ",
            "EXPORT ",
            "IMPORT ",
        ]
        for keyword in dangerous:
            if keyword in normalized:
                raise ValueError(f"Write operation rejected: query contains {keyword.strip()}")

        # Block unbounded variable-length paths like [*] or [:REL*]
        if re.search(r"\[\s*:?\s*\w*\s*\*\s*\]", stripped):
            raise ValueError(
                "Unbounded variable-length path rejected: use [*1..N] with upper bound"
            )

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

    def _build_synthesis_context(self, question: str, kg_results: dict, query_plan: dict) -> str:
        """Build the synthesis prompt for Claude (used by both blocking and streaming)."""
        context = f"""Query Type: {query_plan["type"]}
Cypher: {query_plan["cypher"]}

Sources: {", ".join(kg_results.get("sources", [])[:5])}

Entities found: {json.dumps(kg_results.get("entities", [])[:10], indent=2)}

Facts:
{chr(10).join(f"- {fact}" for fact in kg_results.get("facts", [])[:10])}

Raw results: {json.dumps(kg_results.get("raw", [])[:5], indent=2, default=str)}
"""

        return f"""Using the knowledge graph query results below, answer this question concisely.

Question: {question}

Knowledge Graph Results:
{context}

Provide a clear, factual answer citing the sources. If the KG has no relevant data, say so."""

    def _synthesize_answer(self, question: str, kg_results: dict, query_plan: dict) -> str:
        """Use Claude to synthesize natural language answer from KG results."""
        # Handle error case
        if "error" in kg_results:
            return f"Query execution failed: {kg_results['error']}"

        prompt = self._build_synthesis_context(question, kg_results, query_plan)

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

    # ------------------------------------------------------------------
    # Entity and relationship methods
    # ------------------------------------------------------------------

    def find_entity(self, entity_name: str) -> dict | None:
        """
        Find an entity by name.

        Args:
            entity_name: Entity name to search for

        Returns:
            Entity details with type, properties, and source articles
        """
        self._check_open()
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
            "properties": _safe_json_loads(row["properties"]),
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
        self._check_open()
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
        self._check_open()
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

        Supports both article title lookups (fast path) and arbitrary free-text
        queries. When the query matches an existing article title, the embedding
        from that article's first section is used directly. Otherwise, an
        embedding is generated on the fly using sentence-transformers.

        Args:
            query: Search query -- an article title or arbitrary free text
            top_k: Number of results

        Returns:
            List of similar articles with similarity scores
        """
        self._check_open()
        if not isinstance(top_k, int) or not (1 <= top_k <= 500):
            raise ValueError(f"top_k must be an integer between 1 and 500, got {top_k!r}")

        # Fast path: use an existing article's section embedding
        result = self.conn.execute(
            """
            MATCH (a:Article {title: $query})-[:HAS_SECTION]->(s:Section)
            RETURN s.embedding AS embedding
            LIMIT 1
            """,
            {"query": query},
        )

        df = result.get_as_df()
        if not df.empty:
            query_embedding = df.iloc[0]["embedding"]
        else:
            # Fallback: generate embedding on the fly for free-text queries
            logger.info(f"No article titled {query!r}; generating embedding on the fly")
            generator = self._get_embedding_generator()
            embeddings = generator.generate([query])
            query_embedding = embeddings[0].tolist()

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
                    "similarity": max(0.0, min(1.0, 1.0 - distance)),
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
        """Close database connection and release embedding model if loaded."""
        self.conn = None  # type: ignore[assignment]
        self.db = None  # type: ignore[assignment]
        self._embedding_generator = None
