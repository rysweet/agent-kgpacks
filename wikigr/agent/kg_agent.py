"""
Knowledge Graph Agent - Query WikiGR using natural language.

Simple library approach: direct Kuzu access + Claude for synthesis.
No MCP server, no daemon, just a Python class.
"""

import json
import logging
import re
import time
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
        use_enhancements: bool = False,
        few_shot_path: str | None = None,
        enable_reranker: bool = True,
        enable_multidoc: bool = True,
        enable_fewshot: bool = True,
    ):
        """
        Initialize agent with database connection and Claude API.

        Args:
            db_path: Path to WikiGR Kuzu database
            anthropic_api_key: Anthropic API key (or from ANTHROPIC_API_KEY env var)
            read_only: Open database in read-only mode (allows concurrent access during expansion)
            use_enhancements: Enable Phase 1 enhancements (reranking, multi-doc, few-shot)
            few_shot_path: Path to few-shot examples JSON (default: data/few_shot/physics_examples.json)
            enable_reranker: Enable graph reranker (default True when use_enhancements=True)
            enable_multidoc: Enable multi-doc synthesizer (default True when use_enhancements=True)
            enable_fewshot: Enable few-shot examples (default True when use_enhancements=True)
        """
        self.db = kuzu.Database(db_path, read_only=read_only)
        self.conn = kuzu.Connection(self.db)
        self.claude = Anthropic(api_key=anthropic_api_key)
        self._embedding_generator = None
        self._plan_cache: dict[str, dict] = {}
        self.use_enhancements = use_enhancements
        self.enable_reranker = enable_reranker
        self.enable_multidoc = enable_multidoc
        self.enable_fewshot = enable_fewshot

        # Initialize enhancement modules if enabled
        if use_enhancements:
            from wikigr.agent.few_shot import FewShotManager
            from wikigr.agent.multi_doc_synthesis import MultiDocSynthesizer
            from wikigr.agent.reranker import GraphReranker

            self.reranker = GraphReranker(self.conn) if enable_reranker else None
            self.synthesizer = MultiDocSynthesizer(self.conn) if enable_multidoc else None
            if enable_fewshot:
                few_shot_examples = few_shot_path or "data/few_shot/physics_examples.json"
                self.few_shot = FewShotManager(few_shot_examples)
            else:
                self.few_shot = None
            active = [
                c for c, e in [
                    ("reranker", enable_reranker),
                    ("multi-doc", enable_multidoc),
                    ("few-shot", enable_fewshot),
                ] if e
            ]
            logger.info(f"Phase 1 enhancements enabled: {', '.join(active) or 'none'}")
        else:
            self.reranker = None
            self.synthesizer = None
            self.few_shot = None

        logger.info(
            f"KnowledgeGraphAgent initialized with db: {db_path} (read_only={read_only}, use_enhancements={use_enhancements})"
        )

    @classmethod
    def from_connection(
        cls, conn: kuzu.Connection, claude_client: Anthropic
    ) -> "KnowledgeGraphAgent":
        """Create an agent from an existing connection (no DB lifecycle management).

        Use this when the connection is managed externally (e.g., FastAPI dependency
        injection). All attributes are properly initialized, avoiding the fragile
        __new__() pattern.
        """
        agent = cls.__new__(cls)
        agent.db = None
        agent.conn = conn
        agent.claude = claude_client
        agent._embedding_generator = None
        agent._plan_cache = {}
        agent.use_enhancements = False
        agent.enable_reranker = True
        agent.enable_multidoc = True
        agent.enable_fewshot = True
        agent.reranker = None
        agent.synthesizer = None
        agent.few_shot = None
        return agent

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

        t_start = time.perf_counter()

        # Step 1: PRIMARY = Vector Search; FALLBACK = LLM-generated Cypher
        # Vector search reduces the 30% query failure rate from bad Cypher generation.
        # Fall back to LLM Cypher only when vector confidence is low (< 0.6 cosine similarity).
        t_plan_start = time.perf_counter()
        vector_kg_results, max_similarity = self._vector_primary_retrieve(question, max_results)
        use_vector_primary = vector_kg_results is not None and max_similarity >= 0.6

        if use_vector_primary:
            kg_results = vector_kg_results
            query_plan = {
                "type": "vector_search",
                "cypher": "CALL QUERY_VECTOR_INDEX('Section', 'embedding_idx', $query, K) RETURN *",
                "cypher_params": {"q": question},
            }
            logger.info(f"Vector primary retrieval succeeded (max_similarity={max_similarity:.3f})")
        else:
            if vector_kg_results is not None:
                logger.info(
                    f"Vector search low confidence (max_similarity={max_similarity:.3f} < 0.6), "
                    "falling back to LLM Cypher"
                )
            else:
                logger.info("Vector search returned no results, falling back to LLM Cypher")
            query_plan = self._plan_query(question)

        t_plan = time.perf_counter() - t_plan_start

        # Step 2: Execute Cypher query (only when LLM Cypher fallback is used)
        t_exec_start = time.perf_counter()
        if not use_vector_primary:
            kg_results = self._execute_query(
                query_plan["cypher"], max_results, query_plan.get("cypher_params")
            )

        # Phase 2 Fix: Direct title matching as primary retrieval boost
        # Extract key terms from question and look up articles directly
        try:
            direct_results = self._direct_title_lookup(question)
            existing_sources = set(kg_results.get("sources", []))
            for src in direct_results:
                if src not in existing_sources:
                    kg_results.setdefault("sources", []).insert(0, src)  # Prepend direct matches
                    existing_sources.add(src)
        except Exception as e:
            logger.debug(f"Direct title lookup failed: {e}")

        # Augment with hybrid retrieval for query types that benefit from broader context.
        # Skip for entity_search and entity_relationships which already have precise Cypher.
        query_type = query_plan.get("type", "")
        skip_hybrid = query_type in ("entity_search", "entity_relationships")
        try:
            hybrid_results = {} if skip_hybrid else self._hybrid_retrieve(question, max_results)
            # Merge hybrid sources into KG results (deduplicated)
            existing_sources = set(kg_results.get("sources", []))
            for src in hybrid_results.get("sources", []):
                if src not in existing_sources:
                    kg_results.setdefault("sources", []).append(src)
                    existing_sources.add(src)
            # Add hybrid facts
            existing_facts = set(kg_results.get("facts", []))
            for fact in hybrid_results.get("facts", []):
                if fact not in existing_facts:
                    kg_results.setdefault("facts", []).append(fact)
        except Exception as e:
            logger.debug(f"Hybrid retrieval augmentation failed: {e}")

        t_exec = time.perf_counter() - t_exec_start

        # Step 2.5: Apply Phase 1 enhancements (ADAPTIVE approach)
        # Key insight: enhancements should AUGMENT good retrieval, not replace it.
        # We preserve original sources and only ADD enhanced results via fusion.
        few_shot_examples = []
        if self.use_enhancements:
            t_enhance_start = time.perf_counter()
            try:
                original_sources = list(kg_results.get("sources", []))

                # Enhancement 1: Reciprocal Rank Fusion (RRF) instead of replacement
                # Combine original vector ranking with graph centrality ranking
                # RRF formula: score = sum(1 / (k + rank_i)) across all rankings
                if original_sources:
                    rrf_k = 60  # Standard RRF constant
                    rrf_scores: dict[str, float] = {}

                    # Original vector ranking contribution
                    for rank, src in enumerate(original_sources[:10]):
                        rrf_scores[src] = rrf_scores.get(src, 0) + 1.0 / (rrf_k + rank)

                    # Graph centrality ranking contribution (lower weight)
                    if self.reranker is not None:
                        try:
                            centrality = self.reranker.calculate_centrality(original_sources[:10])
                            sorted_by_centrality = sorted(
                                centrality.items(), key=lambda x: x[1], reverse=True
                            )
                            for rank, (src, _score) in enumerate(sorted_by_centrality):
                                rrf_scores[src] = rrf_scores.get(src, 0) + 0.5 / (rrf_k + rank)
                        except Exception as e:
                            logger.debug(f"Centrality calculation failed: {e}")

                    # Sort by fused score, but PRESERVE original top result
                    fused = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
                    fused_sources = [src for src, _ in fused[:5]]

                    # Adaptive: only use fused ranking if top result changed AND
                    # original top result is still in top 3 (don't lose good matches)
                    if original_sources and original_sources[0] in fused_sources[:3]:
                        kg_results["sources"] = fused_sources
                    else:
                        # Original top result would be demoted too far - keep original
                        logger.debug("RRF would demote top result, keeping original ranking")

                # Enhancement 2: Conditional multi-doc expansion
                # Only expand if we have a HIGH-CONFIDENCE top result (appears in both rankings)
                if self.synthesizer is not None and len(kg_results.get("sources", [])) >= 1:
                    seed_title = kg_results["sources"][0]
                    try:
                        result = self.conn.execute(
                            "MATCH (a:Article {title: $title})-[:LINKS_TO]->(b:Article) "
                            "RETURN b.title AS title LIMIT 2",
                            {"title": seed_title},
                        )
                        df = result.get_as_df()
                        if not df.empty:
                            existing = set(kg_results["sources"])
                            for rt in df["title"].tolist():
                                if rt not in existing and len(kg_results["sources"]) < 7:
                                    kg_results["sources"].append(rt)
                                    existing.add(rt)
                    except Exception as e:
                        logger.debug(f"Multi-doc expansion failed: {e}")

                # Enhancement 3: Few-shot examples (always safe - they guide format, not content)
                if self.few_shot is not None:
                    few_shot_examples = self.few_shot.find_similar_examples(question, k=2)

                t_enhance = time.perf_counter() - t_enhance_start
                logger.info(f"Adaptive enhancements applied in {t_enhance:.2f}s")
            except Exception as e:
                logger.warning(f"Enhancement pipeline failed, using standard retrieval: {e}")
                few_shot_examples = []

        # Step 3: Synthesize answer with Claude
        t_synth_start = time.perf_counter()
        answer = self._synthesize_answer(
            question, kg_results, query_plan, few_shot_examples=few_shot_examples
        )
        t_synth = time.perf_counter() - t_synth_start

        t_total = time.perf_counter() - t_start

        # Structured monitoring log
        logger.info(
            "query_monitor: type=%s total=%.2fs plan=%.2fs exec=%.2fs synth=%.2fs "
            "sources=%d entities=%d facts=%d fallback=%s question=%r",
            query_plan.get("type", "unknown"),
            t_total,
            t_plan,
            t_exec,
            t_synth,
            len(kg_results.get("sources", [])),
            len(kg_results.get("entities", [])),
            len(kg_results.get("facts", [])),
            kg_results.get("fallback", False),
            question[:80],
        )

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

        t_start = time.perf_counter()
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

        t_total = time.perf_counter() - t_start
        logger.info(
            "graph_query_monitor: total=%.2fs hops=%d seeds=%d articles=%d question=%r",
            t_total,
            max_hops,
            len(seed_titles),
            len(context_parts),
            question[:80],
        )

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
        """Use Claude to classify question and generate Cypher query.

        Results are cached by normalized question text (lowered, stripped)
        to avoid redundant Claude API calls for repeated questions.
        """
        cache_key = question.strip().lower()
        if cache_key in self._plan_cache:
            # Move to end for LRU ordering
            self._plan_cache[cache_key] = self._plan_cache.pop(cache_key)
            logger.info(f"Query plan cache hit for: {cache_key[:60]}")
            return self._plan_cache[cache_key]

        plan = self._plan_query_uncached(question)

        # LRU eviction: remove oldest entry when cache is full
        if len(self._plan_cache) >= 128:
            oldest = next(iter(self._plan_cache))
            del self._plan_cache[oldest]
        self._plan_cache[cache_key] = plan

        return plan

    def _plan_query_uncached(self, question: str) -> dict:
        """Generate a fresh query plan via Claude API (uncached)."""
        prompt = f"""You are a Cypher query generator for a Kuzu graph database (NOT Neo4j).

The graph schema:
- Article (title STRING PK, category STRING, word_count INT32)
- Entity (entity_id STRING PK, name STRING, type STRING, description STRING)
- Fact (fact_id STRING PK, content STRING)
- Section (section_id STRING PK, title STRING, content STRING, embedding DOUBLE[384], level INT32, word_count INT32)
- Relationships: HAS_ENTITY, HAS_FACT, ENTITY_RELATION (relation STRING, context STRING), LINKS_TO (link_type STRING), HAS_SECTION (section_index INT32)

IMPORTANT Kuzu syntax rules:
- Use $param for parameters (NOT {{param}})
- Use lower() for case-insensitive matching
- Variable-length paths: [:REL*1..3] (NOT [:REL*])
- No TYPE() function — use relationship property r.relation instead
- No apoc.* functions

Example queries for each type:

1. entity_search: MATCH (e:Entity) WHERE lower(e.name) CONTAINS lower($name) RETURN e.name AS name, e.type AS type LIMIT 10

2. relationship_path: MATCH (a:Entity)-[r:ENTITY_RELATION]->(b:Entity) WHERE lower(a.name) CONTAINS lower($source) RETURN a.name AS source, r.relation AS relation, b.name AS target LIMIT 10

3. fact_retrieval: MATCH (a:Article)-[:HAS_FACT]->(f:Fact) WHERE lower(a.title) CONTAINS lower($title) RETURN f.content AS fact, a.title AS source LIMIT 10

4. entity_relationships: MATCH (e:Entity)-[r:ENTITY_RELATION]->(t:Entity) WHERE lower(e.name) CONTAINS lower($entity) AND r.relation = $relation RETURN e.name AS source, r.relation AS relation, t.name AS target LIMIT 10

5. semantic_search: MATCH (a:Article) WHERE lower(a.title) CONTAINS lower($q) RETURN a.title AS title, a.category AS category LIMIT 10

Question: {question}

You MUST return ONLY valid JSON in this exact format (no extra text):
{{
  "type": "entity_search",
  "cypher": "MATCH ... RETURN ...",
  "explanation": "Why this query"
}}

Use $q as the default parameter name. Return ONLY the JSON, nothing else."""

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
            parsed = json.loads(content)
            # Validate required keys; fall back if missing
            if not isinstance(parsed, dict) or "cypher" not in parsed or "type" not in parsed:
                logger.warning(
                    f"Claude response missing required keys: {list(parsed.keys()) if isinstance(parsed, dict) else type(parsed)}"
                )
                return {
                    "type": "entity_search",
                    "cypher": "MATCH (a:Article) WHERE lower(a.title) CONTAINS lower($q) RETURN a.title AS title LIMIT 10",
                    "cypher_params": {"q": question},
                    "explanation": "Fallback: Claude response missing 'type' or 'cypher' key",
                }
            # Always ensure cypher_params includes the question as $q
            if "cypher_params" not in parsed:
                parsed["cypher_params"] = {"q": question}
            elif "q" not in parsed["cypher_params"]:
                parsed["cypher_params"]["q"] = question
            return parsed
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
        """Execute Cypher query and structure results.

        If the primary query fails (e.g., invalid Cypher from LLM), falls back
        to a simple title-contains search so the agent can still provide answers.
        """
        try:
            self._validate_cypher(cypher)
            result = self.conn.execute(cypher, params or {})
            df = result.get_as_df()
        except Exception as e:
            logger.warning(f"Primary query failed ({type(e).__name__}: {e}), trying fallback")
            return self._execute_fallback_query(params, limit, primary_error=str(e))

        if df.empty:
            return {"sources": [], "entities": [], "facts": [], "raw": []}

        # Structure results based on columns
        raw_records = df.to_dict(orient="records")[:limit]
        structured: dict[str, Any] = {
            "sources": [],
            "entities": [],
            "facts": [],
            "raw": raw_records,
        }

        # Extract sources (article titles) - handle both columns and nested node objects
        for record in raw_records:
            for key, value in record.items():
                if "title" in key.lower() and isinstance(value, str):
                    structured["sources"].append(value)
                elif isinstance(value, dict) and value.get("_label") == "Article":
                    title = value.get("title")
                    if title:
                        structured["sources"].append(title)
                # Handle string values in 'source' or 'target' columns as entity names
                elif key.lower() in ("source", "target") and isinstance(value, str):
                    structured["sources"].append(value)

        structured["sources"] = list(set(structured["sources"]))[:limit]

        # Extract entities - handle flexible column names (name, e.name, entity, etc.)
        name_cols = [c for c in df.columns if "name" in c.lower() or "entity" in c.lower()]
        if name_cols:
            for _, row in df.iterrows():
                name = row.get(name_cols[0])
                if name and isinstance(name, str):
                    type_cols = [c for c in df.columns if "type" in c.lower()]
                    entity_type = row.get(type_cols[0], "unknown") if type_cols else "unknown"
                    structured["entities"].append({"name": name, "type": entity_type})

        # Extract facts from content, fact, or relation columns
        fact_cols = [c for c in df.columns if c.lower() in ("content", "fact", "relation")]
        if fact_cols:
            structured["facts"] = df[fact_cols[0]].dropna().tolist()[:limit]

        return structured

    def _execute_fallback_query(self, params: dict | None, limit: int, primary_error: str) -> dict:
        """Fallback query when LLM-generated Cypher fails."""
        search_term = ""
        if params:
            # Use any string parameter as search term
            for v in params.values():
                if isinstance(v, str) and len(v) > 1:
                    search_term = v
                    break

        if not search_term:
            return {
                "sources": [],
                "entities": [],
                "facts": [],
                "raw": [],
                "error": f"Primary query failed: {primary_error}",
            }

        try:
            result = self.conn.execute(
                "MATCH (a:Article) WHERE lower(a.title) CONTAINS lower($q) "
                "RETURN a.title AS title, a.category AS category LIMIT $limit",
                {"q": search_term, "limit": limit},
            )
            df = result.get_as_df()
            if df.empty:
                return {
                    "sources": [],
                    "entities": [],
                    "facts": [],
                    "raw": [],
                    "error": f"Primary query failed and fallback found no results: {primary_error}",
                }

            records = df.to_dict(orient="records")[:limit]
            return {
                "sources": [r["title"] for r in records if r.get("title")],
                "entities": [],
                "facts": [],
                "raw": records,
                "fallback": True,
                "primary_error": primary_error,
            }
        except Exception as fallback_error:
            logger.error(f"Fallback query also failed: {fallback_error}")
            return {
                "sources": [],
                "entities": [],
                "facts": [],
                "raw": [],
                "error": f"Both primary and fallback queries failed: {primary_error}",
            }

    def _direct_title_lookup(self, question: str) -> list[str]:
        """Phase 2: Direct article title matching for better retrieval.

        Extracts key noun phrases from the question and looks up articles
        with matching titles. This catches cases where the LLM query planner
        generates bad Cypher but the answer is in an obviously-named article.
        """
        import re

        # Extract potential article titles from question
        # Strip common question prefixes
        cleaned = re.sub(
            r"^(what is|what are|explain|describe|define|how does|how do|what does|"
            r"who is|who was|when was|where is|why is|why does|tell me about)\s+",
            "",
            question.lower(),
            flags=re.IGNORECASE,
        ).rstrip("?. ")

        # Try exact title match first, then partial
        candidates = []
        try:
            # Exact match (case-insensitive)
            result = self.conn.execute(
                "MATCH (a:Article) WHERE lower(a.title) = $q RETURN a.title",
                {"q": cleaned},
            )
            df = result.get_as_df()
            if not df.empty:
                candidates.extend(df["a.title"].tolist())

            # Partial match if no exact match
            if not candidates:
                result = self.conn.execute(
                    "MATCH (a:Article) WHERE lower(a.title) CONTAINS $q "
                    "RETURN a.title ORDER BY length(a.title) ASC LIMIT 3",
                    {"q": cleaned},
                )
                df = result.get_as_df()
                if not df.empty:
                    candidates.extend(df["a.title"].tolist())
        except Exception as e:
            logger.debug(f"Direct title lookup query failed: {e}")

        return candidates[:3]

    def _vector_primary_retrieve(
        self, question: str, max_results: int
    ) -> tuple[dict | None, float]:
        """Attempt vector search as primary retrieval.

        Args:
            question: Natural language question.
            max_results: Maximum results to return.

        Returns:
            (kg_results_dict, max_similarity) or (None, 0.0) on failure.
            max_similarity is the highest cosine similarity among results (0.0–1.0).
        """
        try:
            vector_results = self.semantic_search(question, top_k=max_results)
            if not vector_results:
                return None, 0.0

            max_similarity = max(r.get("similarity", 0.0) for r in vector_results)
            sources = [r["title"] for r in vector_results]
            return {
                "sources": sources,
                "entities": [],
                "facts": [],
                "raw": [
                    {"title": r["title"], "score": r.get("similarity", 0.0)}
                    for r in vector_results
                ],
            }, max_similarity
        except Exception as e:
            logger.warning(f"Vector primary retrieve failed: {e}")
            return None, 0.0

    def _hybrid_retrieve(
        self,
        question: str,
        max_results: int = 10,
        vector_weight: float = 0.5,
        graph_weight: float = 0.3,
        keyword_weight: float = 0.2,
    ) -> dict:
        """Combine vector, graph, and keyword retrieval for richer results.

        Args:
            question: Natural language question.
            max_results: Maximum articles to return.
            vector_weight: Weight for vector similarity signal (0-1).
            graph_weight: Weight for graph proximity signal (0-1).
            keyword_weight: Weight for keyword match signal (0-1).

        Returns:
            KG results dict with sources, entities, facts, raw.
        """
        scored: dict[str, float] = {}

        # Signal 1: Vector search (semantic similarity via existing semantic_search)
        try:
            vector_results = self.semantic_search(question, top_k=max_results)
            for r in vector_results:
                title = r.get("article", r.get("title", ""))
                if title:
                    scored[title] = scored.get(title, 0) + vector_weight * r.get("similarity", 0.5)
        except Exception as e:
            logger.warning(f"Vector search failed in hybrid retrieve: {e}")

        # Signal 2: Graph traversal (follow LINKS_TO from vector hits)
        seed_titles = list(scored.keys())[:3]
        for seed in seed_titles:
            try:
                result = self.conn.execute(
                    "MATCH (seed:Article {title: $title})-[:LINKS_TO]->(neighbor:Article) "
                    "RETURN neighbor.title AS title LIMIT $limit",
                    {"title": seed, "limit": max_results},
                )
                df = result.get_as_df()
                for _, row in df.iterrows():
                    title = row["title"]
                    if title:
                        scored[title] = scored.get(title, 0) + graph_weight * 0.5
            except Exception as e:
                logger.debug(f"Graph traversal failed for '{seed}': {e}")

        # Signal 3: Keyword match (title contains)
        keywords = [w for w in question.split() if len(w) > 3]
        for kw in keywords[:3]:
            try:
                result = self.conn.execute(
                    "MATCH (a:Article) WHERE lower(a.title) CONTAINS lower($kw) "
                    "RETURN a.title AS title LIMIT $limit",
                    {"kw": kw, "limit": max_results},
                )
                df = result.get_as_df()
                for _, row in df.iterrows():
                    title = row["title"]
                    if title:
                        scored[title] = scored.get(title, 0) + keyword_weight * 0.7
            except Exception as e:
                logger.debug(f"Keyword search failed for '{kw}': {e}")

        # Rank by combined score
        ranked = sorted(scored.items(), key=lambda x: x[1], reverse=True)[:max_results]
        source_titles = [title for title, _score in ranked]

        # Fetch facts for top sources
        facts: list[str] = []
        for title in source_titles[:5]:
            try:
                result = self.conn.execute(
                    "MATCH (a:Article {title: $title})-[:HAS_FACT]->(f:Fact) "
                    "RETURN f.content AS content LIMIT 3",
                    {"title": title},
                )
                df = result.get_as_df()
                facts.extend(df["content"].dropna().tolist())
            except Exception:
                pass

        return {
            "sources": source_titles,
            "entities": [],
            "facts": facts,
            "raw": [{"title": t, "score": s} for t, s in ranked[:10]],
        }

    def _fetch_source_text(self, source_titles: list[str], max_articles: int = 5) -> str:
        """Fetch original section text for source articles (batched, single query).

        Retrieves the lead section (index 0) content for each source article,
        providing Claude with the original Wikipedia text for grounded synthesis.
        """
        self._check_open()
        titles = source_titles[:max_articles]
        if not titles:
            return ""
        try:
            result = self.conn.execute(
                "MATCH (a:Article)-[:HAS_SECTION {section_index: 0}]->(s:Section) "
                "WHERE a.title IN $titles "
                "RETURN a.title AS title, s.content AS content",
                {"titles": titles},
            )
            df = result.get_as_df()
            texts: list[str] = []
            for _, row in df.iterrows():
                content = row.get("content")
                title = row.get("title", "")
                if content:
                    truncated = content[:500] + ("..." if len(content) > 500 else "")
                    texts.append(f"## {title}\n{truncated}")
            return "\n\n".join(texts)
        except Exception as e:
            logger.warning(f"Failed to fetch source text: {e}")
            return ""

    def _build_synthesis_context(
        self,
        question: str,
        kg_results: dict,
        query_plan: dict,
        few_shot_examples: list[dict] | None = None,
    ) -> str:
        """Build the synthesis prompt for Claude (used by both blocking and streaming).

        Includes both structured KG results (entities, facts, triples) AND
        the original article section text for grounded, accurate synthesis.
        Optionally includes few-shot examples when Phase 1 enhancements are enabled.
        """
        sources = kg_results.get("sources", [])[:5]

        # Fetch original article text for grounded synthesis
        source_text = self._fetch_source_text(sources)

        # Build few-shot examples section if provided
        few_shot_section = ""
        if few_shot_examples:
            few_shot_section = "\nHere are similar questions and their answers:\n\n"
            for i, example in enumerate(few_shot_examples[:3], 1):
                few_shot_section += f"Example {i}:\n"
                few_shot_section += f"Q: {example.get('question', example.get('query', ''))}\n"
                few_shot_section += f"A: {example['answer']}\n\n"

        # Use enriched multi-doc context if available, otherwise standard context
        if "enriched_context" in kg_results:
            context = f"""Query Type: {query_plan["type"]}

{kg_results["enriched_context"]}

Entities found: {json.dumps(kg_results.get("entities", [])[:10], indent=2)}

Facts:
{chr(10).join(f"- {fact}" for fact in kg_results.get("facts", [])[:10])}
"""
        else:
            context = f"""Query Type: {query_plan["type"]}
Cypher: {query_plan["cypher"]}

Sources: {", ".join(sources)}

Entities found: {json.dumps(kg_results.get("entities", [])[:10], indent=2)}

Facts:
{chr(10).join(f"- {fact}" for fact in kg_results.get("facts", [])[:10])}

Raw results: {json.dumps(kg_results.get("raw", [])[:5], indent=2, default=str)}
"""

        # Add original text if available
        if source_text:
            context += f"""
Original Article Text (for grounding):
{source_text}
"""

        return f"""{few_shot_section}Using the knowledge graph results AND original article text below, answer this question concisely and accurately.

Question: {question}

Knowledge Graph Results:
{context}

Provide a clear, factual answer grounded in the source text. Cite specific articles. If the KG has no relevant data, say so."""

    def _synthesize_answer(
        self,
        question: str,
        kg_results: dict,
        query_plan: dict,
        few_shot_examples: list[dict] | None = None,
    ) -> str:
        """Use Claude to synthesize natural language answer from KG results."""
        # Handle error case
        if "error" in kg_results:
            return f"Query execution failed: {kg_results['error']}"

        prompt = self._build_synthesis_context(
            question, kg_results, query_plan, few_shot_examples=few_shot_examples or []
        )

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
            RETURN e.name AS name, e.type AS type, e.description AS description,
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
            "properties": _safe_json_loads(row.get("description", "")),
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
        self._plan_cache.clear()
