"""
Knowledge Graph Agent - Query WikiGR using natural language.

Simple library approach: direct LadybugDB access + Claude for synthesis.
No MCP server, no daemon, just a Python class.
"""

import json
import logging
import re
import time
from typing import Any

import real_ladybug as kuzu
from anthropic import Anthropic, APIConnectionError, APIStatusError, APITimeoutError

# Pre-compiled regex used in _direct_title_lookup — avoids recompilation on every query() call.
_QUESTION_PREFIX_RE = re.compile(
    r"^(what is|what are|explain|describe|define|how does|how do|what does|"
    r"who is|who was|when was|where is|why is|why does|tell me about)\s+",
    re.IGNORECASE,
)

# Pre-compiled constants for _validate_cypher — avoids recreating on every call.
_CYPHER_BLOCKED_OPS: frozenset[str] = frozenset(
    {"CREATE", "DELETE", "DROP", "SET", "MERGE", "REMOVE", "DETACH"}
)
_CYPHER_STRIP_DQ = re.compile(r'"[^"]*"')
_CYPHER_STRIP_SQ = re.compile(r"'[^']*'")
_CYPHER_TOKENS_RE = re.compile(r"\b[A-Za-z]+\b")
_CYPHER_UNBOUNDED_PATH_RE = re.compile(r"\[[\w:]*\*[^\]]*\]")

logger = logging.getLogger(__name__)


def _safe_json_loads(value: object) -> dict:
    """Parse JSON string to dict, returning {} on any failure."""
    if not isinstance(value, str):
        return value if isinstance(value, dict) else {}
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return {}


def _strip_markdown_fences(text: str) -> str:
    """Strip ```json or ``` fences from LLM response text."""
    if "```json" in text:
        return text.split("```json")[1].split("```")[0].strip()
    if "```" in text:
        return text.split("```")[1].split("```")[0].strip()
    return text


class KnowledgeGraphAgent:
    """Agent that queries WikiGR knowledge graph and synthesizes answers."""

    # Default synthesis model — Opus for best quality
    DEFAULT_MODEL = "claude-opus-4-6"

    # --- Extracted constants (avoid magic numbers) ---
    VECTOR_CONFIDENCE_THRESHOLD = 0.6
    CONTEXT_CONFIDENCE_THRESHOLD = 0.5
    PLAN_CACHE_MAX_SIZE = 128
    MAX_ARTICLE_CHARS = 3000
    PLAN_MAX_TOKENS = 512
    SYNTHESIS_MAX_TOKENS = 1024
    SEED_EXTRACT_MAX_TOKENS = 256

    # --- Content quality filtering ---
    CONTENT_QUALITY_THRESHOLD = 0.3
    STOP_WORDS: frozenset[str] = frozenset(
        {
            "a",
            "an",
            "the",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "shall",
            "can",
            "not",
            "no",
            "nor",
            "so",
            "yet",
            "both",
            "either",
            "neither",
            "as",
            "if",
            "then",
            "than",
            "that",
            "this",
            "these",
            "those",
            "it",
            "its",
            "i",
            "we",
            "you",
            "he",
            "she",
            "they",
            "me",
            "us",
            "him",
            "her",
            "them",
            "my",
            "our",
            "your",
            "his",
            "their",
            "what",
            "which",
            "who",
            "whom",
            "when",
            "where",
            "why",
            "how",
            "all",
            "any",
            "each",
            "few",
            "more",
            "most",
            "other",
            "some",
            "such",
            "up",
            "out",
            "about",
            "into",
            "through",
            "after",
            "before",
            "between",
            "tell",
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
    )

    def __init__(
        self,
        db_path: str,
        anthropic_api_key: str | None = None,
        read_only: bool = True,
        use_enhancements: bool = True,
        few_shot_path: str | None = None,
        enable_reranker: bool = True,
        enable_multidoc: bool = True,
        enable_fewshot: bool = True,
        enable_cross_encoder: bool = False,
        synthesis_model: str | None = None,
        cypher_pack_path: str | None = None,
        enable_multi_query: bool = False,
    ):
        """
        Initialize agent with database connection and Claude API.

        Args:
            db_path: Path to WikiGR LadybugDB database
            anthropic_api_key: Anthropic API key (or from ANTHROPIC_API_KEY env var)
            read_only: Open database in read-only mode (allows concurrent access during expansion)
            use_enhancements: Enable Phase 1 enhancements (reranking, multi-doc, few-shot)
            few_shot_path: Path to few-shot examples JSON (auto-detected from pack dir when None)
            enable_reranker: Enable graph reranker (default True when use_enhancements=True)
            enable_multidoc: Enable multi-doc synthesizer (default True when use_enhancements=True)
            enable_fewshot: Enable few-shot examples (default True when use_enhancements=True)
            enable_cross_encoder: Enable cross-encoder reranking after vector retrieval
                (default False — opt-in; only active when use_enhancements=True)
            synthesis_model: Claude model for all synthesis/planning (default: claude-opus-4-6)
            cypher_pack_path: Path to OpenCypher expert pack examples for RAG-augmented generation
            enable_multi_query: Generate alternative query phrasings via Claude Haiku to improve recall.
                **Data notice:** when True, user questions are sent to the Anthropic API for expansion.
                Keep False for deployments with data-residency, PII, or offline constraints.
        """
        self.db = kuzu.Database(db_path, read_only=read_only)
        self.conn = kuzu.Connection(self.db)
        self._load_extensions()
        self.claude = Anthropic(api_key=anthropic_api_key)
        self.synthesis_model = synthesis_model or self.DEFAULT_MODEL
        self._embedding_generator = None
        self._plan_cache: dict[str, dict] = {}
        self.token_usage = {"input_tokens": 0, "output_tokens": 0, "api_calls": 0}
        self.use_enhancements = use_enhancements
        self.enable_reranker = enable_reranker
        self.enable_multidoc = enable_multidoc
        self.enable_fewshot = enable_fewshot
        self.enable_cross_encoder = enable_cross_encoder
        self.enable_multi_query = enable_multi_query

        # Warn if enable_* flags are set but use_enhancements=False (they have no effect)
        if not use_enhancements and any(
            [
                enable_reranker is not True,
                enable_multidoc is not True,
                enable_fewshot is not True,
                enable_cross_encoder is not False,
            ]
        ):
            logger.warning(
                "enable_reranker/enable_multidoc/enable_fewshot/enable_cross_encoder flags "
                "have no effect when use_enhancements=False. Set use_enhancements=True to use them."
            )

        # Initialize enhancement modules if enabled
        if use_enhancements:
            from wikigr.agent.few_shot import FewShotManager
            from wikigr.agent.multi_doc_synthesis import MultiDocSynthesizer
            from wikigr.agent.reranker import GraphReranker

            self.reranker = GraphReranker(self.conn) if enable_reranker else None
            self.synthesizer = MultiDocSynthesizer(self.conn) if enable_multidoc else None
            if enable_fewshot:
                resolved_path = self._resolve_few_shot_path(few_shot_path, db_path)
                if resolved_path is not None:
                    self.few_shot = FewShotManager(resolved_path)
                else:
                    self.few_shot = None
                    logger.warning(
                        "Few-shot enabled but no examples file found for pack at %s. "
                        "Pass few_shot_path explicitly or add eval/questions.jsonl next to pack.db.",
                        db_path,
                    )
            else:
                self.few_shot = None
            if enable_cross_encoder:
                from wikigr.agent.cross_encoder import CrossEncoderReranker

                self.cross_encoder = CrossEncoderReranker()
            else:
                self.cross_encoder = None
            active = [
                c
                for c, e in [
                    ("reranker", enable_reranker),
                    ("multi-doc", enable_multidoc),
                    ("few-shot", enable_fewshot),
                    ("cross-encoder", enable_cross_encoder),
                ]
                if e
            ]
            logger.info(f"Phase 1 enhancements enabled: {', '.join(active) or 'none'}")
        else:
            self.reranker = None
            self.synthesizer = None
            self.few_shot = None
            self.cross_encoder = None

        # Initialize CypherRAG if a pack path is provided
        self.cypher_rag = self._init_cypher_rag(cypher_pack_path)

        logger.info(
            f"KnowledgeGraphAgent initialized with db: {db_path} (read_only={read_only}, use_enhancements={use_enhancements})"
        )

    def _load_extensions(self):
        """Load required LadybugDB extensions."""
        from bootstrap.schema.ryugraph_schema import load_extensions

        load_extensions(self.conn)

    @staticmethod
    def _resolve_few_shot_path(few_shot_path: str | None, db_path: str) -> str | None:
        """Resolve the few-shot examples file path for the current pack.

        Priority:
        1. Explicit ``few_shot_path`` argument (caller knows best).
        2. ``<pack_dir>/eval/questions.jsonl`` adjacent to ``pack.db``.
        3. Legacy ``data/few_shot/physics_examples.json`` (only if it exists).
        4. None -- caller should disable few-shot gracefully.
        """
        from pathlib import Path

        if few_shot_path is not None:
            if Path(few_shot_path).exists():
                return few_shot_path
            logger.warning("Explicit few_shot_path %s does not exist", few_shot_path)
            return None

        # Auto-detect: look next to the database file
        pack_questions = Path(db_path).parent / "eval" / "questions.jsonl"
        if pack_questions.exists():
            logger.info("Auto-detected few-shot examples: %s", pack_questions)
            return str(pack_questions)

        # Legacy fallback -- only use if the file actually exists
        legacy = Path("data/few_shot/physics_examples.json")
        if legacy.exists():
            logger.info("Using legacy few-shot examples: %s", legacy)
            return str(legacy)

        return None

    @staticmethod
    def _validate_cypher(query: str) -> None:
        """Validate a Cypher query against an allowlist/blocklist.

        Prevents destructive write operations and unbounded variable-length
        path patterns from reaching the database.

        Args:
            query: The Cypher query string to validate.

        Raises:
            ValueError: If the query fails any validation check.
        """
        # Strip string literals to avoid false positives on quoted content.
        stripped = _CYPHER_STRIP_DQ.sub('""', query)
        stripped = _CYPHER_STRIP_SQ.sub("''", stripped)

        upper = stripped.strip().upper()

        # 1. Prefix check — must start with an allowed read keyword.
        if not (upper.startswith("MATCH") or upper.startswith("CALL")):
            raise ValueError("Cypher query must start with MATCH or CALL")

        # 2. Block dangerous write/DDL keywords.
        for token in _CYPHER_TOKENS_RE.findall(stripped):
            if token.upper() in _CYPHER_BLOCKED_OPS:
                raise ValueError(f"Write operation rejected: {token.upper()}")

        # 3. Block unbounded variable-length paths (e.g. [:REL*]).
        if _CYPHER_UNBOUNDED_PATH_RE.search(query):
            raise ValueError("Unbounded variable-length path detected in query")

    def _init_cypher_rag(self, cypher_pack_path: str | None) -> Any:
        """Initialize CypherRAG if a Cypher pattern pack path is provided.

        Args:
            cypher_pack_path: Path to OpenCypher expert pack examples JSON/JSONL.

        Returns:
            CypherRAG instance or None if unavailable.
        """
        if cypher_pack_path is None:
            return None

        from pathlib import Path

        pack_path = Path(cypher_pack_path)
        if not pack_path.exists():
            logger.warning(
                "cypher_pack_path %s does not exist, CypherRAG disabled", cypher_pack_path
            )
            return None

        try:
            from wikigr.agent.cypher_rag import CypherRAG, build_schema_string
            from wikigr.agent.few_shot import FewShotManager

            pattern_manager = FewShotManager(pack_path)
            schema = build_schema_string(self.conn)
            rag = CypherRAG(
                pattern_manager=pattern_manager,
                claude_client=self.claude,
                schema=schema,
                model=self.synthesis_model,
            )
            logger.info(
                "CypherRAG initialized with pack: %s (%d patterns)",
                cypher_pack_path,
                len(pattern_manager.examples),
            )
            return rag
        except (RuntimeError, ImportError) as e:
            logger.warning("CypherRAG initialization failed: %s", e)
            return None

    def _track_response(self, response) -> None:
        """Accumulate token usage from a Claude API response."""
        if not hasattr(self, "token_usage"):
            self.token_usage = {"input_tokens": 0, "output_tokens": 0, "api_calls": 0}
        if hasattr(response, "usage"):
            self.token_usage["input_tokens"] += getattr(response.usage, "input_tokens", 0)
            self.token_usage["output_tokens"] += getattr(response.usage, "output_tokens", 0)
            self.token_usage["api_calls"] += 1

    @classmethod
    def from_connection(
        cls, conn: kuzu.Connection, claude_client: Anthropic
    ) -> "KnowledgeGraphAgent":
        """Create an agent from an existing connection (no DB lifecycle management).

        Use this when the connection is managed externally (e.g., FastAPI dependency
        injection). All attributes are properly initialized, avoiding the fragile
        __new__() pattern.

        **Data notice:** if you set ``agent.enable_multi_query = True`` after construction,
        user questions will be sent to the Anthropic API for query expansion.  Keep the
        default (``False``) for deployments with data-residency, PII, or offline constraints.
        """
        agent = cls.__new__(cls)
        agent.db = None
        agent.conn = conn
        agent.claude = claude_client
        agent._embedding_generator = None
        agent._plan_cache = {}
        agent.use_enhancements = False
        agent.token_usage = {"input_tokens": 0, "output_tokens": 0, "api_calls": 0}
        agent.enable_reranker = True
        agent.enable_multidoc = True
        agent.enable_fewshot = True
        agent.enable_cross_encoder = False
        agent.enable_multi_query = False
        agent.synthesis_model = cls.DEFAULT_MODEL
        agent.reranker = None
        agent.synthesizer = None
        agent.few_shot = None
        agent.cross_encoder = None
        agent.cypher_rag = None
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

    def _safe_query(self, cypher: str, params: dict | None = None, *, log_context: str = "") -> Any:
        """Execute Cypher and return DataFrame, or None on failure.

        Consolidates the repeated try/execute/get_as_df/except pattern.
        Returns the DataFrame when non-empty, or None on empty/error.
        """
        try:
            result = self.conn.execute(cypher, params or {})
            df = result.get_as_df()
            return df if not df.empty else None
        except RuntimeError as e:
            logger.debug("Query failed%s: %s", f" ({log_context})" if log_context else "", e)
            return None

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

        # Step 1: Vector search is ALWAYS the primary retrieval
        # Experiment 2: Remove LLM Cypher entirely — vector + hybrid only.
        t_plan_start = time.perf_counter()
        vector_kg_results, max_similarity = self._vector_primary_retrieve(question, max_results)

        if vector_kg_results is not None:
            kg_results = vector_kg_results
            query_plan = {
                "type": "vector_search",
                "cypher": f"CALL QUERY_VECTOR_INDEX('Section', 'embedding_idx', $emb, {max_results * 3}) RETURN *",
                "cypher_params": {"emb": "<embedding_vector>"},
            }
            logger.info(
                f"Vector retrieval: {len(kg_results.get('sources', []))} sources (max_similarity={max_similarity:.3f})"
            )

            # Confidence gate: skip all pack context injection when similarity is too low
            if max_similarity < self.CONTEXT_CONFIDENCE_THRESHOLD:
                return {
                    "answer": self._synthesize_answer_minimal(question),
                    "sources": [],
                    "entities": [],
                    "facts": [],
                    "cypher_query": query_plan["cypher"],
                    "query_type": "training_only_response",
                    "token_usage": dict(self.token_usage),
                }
        else:
            # Vector search failed entirely — use empty results (hybrid will fill in)
            kg_results = {"sources": [], "entities": [], "facts": [], "raw": []}
            query_plan = {"type": "vector_search", "cypher": "N/A", "cypher_params": {}}
            logger.warning("Vector search returned no results")

        t_plan = time.perf_counter() - t_plan_start

        # Step 2: No LLM Cypher execution — vector results are used directly
        t_exec_start = time.perf_counter()

        # Direct title matching as primary retrieval boost
        try:
            direct_results = self._direct_title_lookup(question)
            existing_sources = set(kg_results.get("sources", []))
            for src in direct_results:
                if src not in existing_sources:
                    kg_results.setdefault("sources", []).insert(0, src)  # Prepend direct matches
                    existing_sources.add(src)
        except RuntimeError as e:
            logger.debug(f"Direct title lookup failed: {e}")

        # ALWAYS augment with hybrid retrieval (no skip for any query type).
        # Pass precomputed vector results to avoid a duplicate semantic_search call.
        _precomputed = (
            [{"title": r["title"], "similarity": r["score"]} for r in kg_results.get("raw", [])]
            if vector_kg_results is not None
            else None
        )
        try:
            hybrid_results = self._hybrid_retrieve(
                question, max_results, _precomputed_vector=_precomputed
            )
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
        except RuntimeError as e:
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
                        except RuntimeError as e:
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
                    df = self._safe_query(
                        "MATCH (a:Article {title: $title})-[:LINKS_TO]->(b:Article) "
                        "RETURN b.title AS title LIMIT 2",
                        {"title": seed_title},
                        log_context="multi-doc expansion",
                    )
                    if df is not None:
                        existing = set(kg_results["sources"])
                        for rt in df["title"].tolist():
                            if rt not in existing and len(kg_results["sources"]) < 7:
                                kg_results["sources"].append(rt)
                                existing.add(rt)

                # Enhancement 3: Few-shot examples (always safe - they guide format, not content)
                if self.few_shot is not None:
                    few_shot_examples = self.few_shot.find_similar_examples(question, k=2)

                t_enhance = time.perf_counter() - t_enhance_start
                logger.info(f"Adaptive enhancements applied in {t_enhance:.2f}s")
            except (RuntimeError, OSError) as e:
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
        logger.debug(
            "query_monitor: type=%s total=%.2fs plan=%.2fs exec=%.2fs synth=%.2fs "
            "sources=%d entities=%d facts=%d question=%r",
            query_plan.get("type", "unknown"),
            t_total,
            t_plan,
            t_exec,
            t_synth,
            len(kg_results.get("sources", [])),
            len(kg_results.get("entities", [])),
            len(kg_results.get("facts", [])),
            question[:80],
        )

        return {
            "answer": answer,
            "sources": kg_results.get("sources", []),
            "entities": kg_results.get("entities", []),
            "facts": kg_results.get("facts", []),
            "cypher_query": query_plan["cypher"],
            "query_type": query_plan["type"],
            "token_usage": dict(self.token_usage),
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
            df = self._safe_query(
                traversal_cypher,
                {"title": seed_title, "limit": max_context_articles},
                log_context=f"traversal for seed '{seed_title}'",
            )
            if df is not None:
                all_related_titles.extend(df["title"].tolist())

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
            df = self._safe_query(
                section_cypher, {"title": title}, log_context=f"section fetch for '{title}'"
            )
            if df is not None:
                sect_content = df.iloc[0]["content"]
                if sect_content:
                    context_parts.append(f"## {title}\n{sect_content}")

        # ------------------------------------------------------------------
        # Step 4: Synthesize the answer with Claude
        # ------------------------------------------------------------------
        combined_context = "\n\n".join(context_parts) if context_parts else "(no context found)"
        answer = self._synthesize_graph_rag_answer(question, combined_context, unique_titles)

        t_total = time.perf_counter() - t_start
        logger.debug(
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

        Raises APIConnectionError, APIStatusError, or APITimeoutError on Claude API failure.
        Raises ValueError if the API returns an empty or unparseable response.
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
                model=self.synthesis_model,
                max_tokens=self.SEED_EXTRACT_MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            self._track_response(response)
        except (APIConnectionError, APIStatusError, APITimeoutError):
            logger.warning("Claude API error in _identify_seed_articles")
            raise

        if not response.content:
            raise ValueError("Empty response from Claude API in _identify_seed_articles")

        text = _strip_markdown_fences(response.content[0].text.strip())

        try:
            titles = json.loads(text)
            if isinstance(titles, list) and all(isinstance(t, str) for t in titles):
                return titles[:3]
        except (json.JSONDecodeError, TypeError) as e:
            raise ValueError(f"Failed to parse seed titles JSON: {text[:200]}") from e

        raise ValueError(f"Unexpected response format from _identify_seed_articles: {text[:200]}")

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
                model=self.synthesis_model,
                max_tokens=self.SYNTHESIS_MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            self._track_response(response)
        except (APIConnectionError, APIStatusError, APITimeoutError) as e:
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
    # Retrieval helpers — delegate to wikigr.agent.retriever
    # ------------------------------------------------------------------

    def _direct_title_lookup(self, question: str) -> list[str]:
        """Phase 2: Direct article title matching for better retrieval.

        Extracts key noun phrases from the question and looks up articles
        with matching titles. This catches cases where the LLM query planner
        generates bad Cypher but the answer is in an obviously-named article.
        """
        from wikigr.agent.retriever import direct_title_lookup

        return direct_title_lookup(self.conn, question)

    def _multi_query_retrieve(self, question: str, max_results: int = 5) -> list[dict]:
        """Retrieve results using original question plus 2 alternative phrasings.

        Generates 2 alternative phrasings via Claude Haiku, runs semantic_search
        for all 3 queries, then deduplicates by title keeping the highest similarity
        score, and returns results sorted descending by similarity.

        Args:
            question: Original natural language question.
            max_results: Maximum results per query (deduplication reduces final count).

        Returns:
            Deduplicated list of result dicts sorted by similarity descending.
        """
        from wikigr.agent.retriever import multi_query_retrieve

        return multi_query_retrieve(
            self.claude,
            self.semantic_search,
            self._track_response,
            question,
            max_results,
        )

    def _vector_primary_retrieve(
        self, question: str, max_results: int
    ) -> tuple[dict | None, float]:
        """Attempt vector search as primary retrieval.

        Args:
            question: Natural language question.
            max_results: Maximum results to return.

        Returns:
            (kg_results_dict, max_similarity) or (None, 0.0) on failure.
            max_similarity is the highest cosine similarity among results (0.0-1.0).
        """
        from wikigr.agent.retriever import vector_primary_retrieve

        return vector_primary_retrieve(
            self.semantic_search,
            self._multi_query_retrieve,
            self.cross_encoder,
            self.enable_multi_query,
            question,
            max_results,
        )

    def _hybrid_retrieve(
        self,
        question: str,
        max_results: int = 10,
        vector_weight: float = 0.5,
        graph_weight: float = 0.3,
        keyword_weight: float = 0.2,
        _precomputed_vector: list[dict] | None = None,
    ) -> dict[str, Any]:
        """Combine vector, graph, and keyword retrieval for richer results.

        Args:
            question: Natural language question.
            max_results: Maximum articles to return.
            vector_weight: Weight for vector similarity signal (0-1).
            graph_weight: Weight for graph proximity signal (0-1).
            keyword_weight: Weight for keyword match signal (0-1).
            _precomputed_vector: Pre-computed semantic_search results to avoid a
                duplicate DB call when the caller already ran vector retrieval.
                Pass None to let this method run its own search.

        Returns:
            KG results dict with sources, entities, facts, raw.
        """
        from wikigr.agent.retriever import hybrid_retrieve

        return hybrid_retrieve(
            self.conn,
            self.semantic_search,
            self.STOP_WORDS,
            question,
            max_results,
            vector_weight,
            graph_weight,
            keyword_weight,
            _precomputed_vector,
        )

    def _score_section_quality(
        self,
        content: str,
        question: str,
        *,
        _q_keywords: frozenset[str] | None = None,
    ) -> float:
        """Score a section's quality for inclusion in synthesis context.

        Args:
            content: Section text content.
            question: User question (used for keyword overlap scoring).
            _q_keywords: Pre-computed question keywords (frozenset). When
                supplied by the caller (e.g. from a batch loop), this avoids
                re-splitting and re-filtering the question on every invocation.

        Returns:
            Quality score in [0.0, 1.0]. Returns 0.0 for stubs under 20 words.
        """
        from wikigr.agent.retriever import score_section_quality

        return score_section_quality(content, question, self.STOP_WORDS, _q_keywords=_q_keywords)

    def _fetch_source_text(
        self,
        source_titles: list[str],
        max_articles: int = 5,
        question: str | None = None,
    ) -> str:
        """Fetch section text for source articles (batched, single query).

        Retrieves ALL section content for each source article, concatenated,
        providing Claude with rich source text for grounded synthesis.
        Falls back to article-level content if sections aren't available.

        When ``question`` is provided, sections below CONTENT_QUALITY_THRESHOLD
        are filtered out before inclusion.
        """
        self._check_open()

        from wikigr.agent.retriever import fetch_source_text

        return fetch_source_text(
            self.conn,
            self._score_section_quality,
            self.STOP_WORDS,
            self.MAX_ARTICLE_CHARS,
            self.CONTENT_QUALITY_THRESHOLD,
            source_titles,
            max_articles,
            question,
        )

    # ------------------------------------------------------------------
    # Synthesis helpers — delegate to wikigr.agent.synthesizer
    # ------------------------------------------------------------------

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
        from wikigr.agent.synthesizer import build_synthesis_context

        return build_synthesis_context(
            self._fetch_source_text,
            question,
            kg_results,
            query_plan,
            few_shot_examples,
        )

    def _synthesize_answer_minimal(self, question: str) -> str:
        """Synthesize answer using Claude's own knowledge when pack has no relevant content."""
        from wikigr.agent.synthesizer import synthesize_answer_minimal

        return synthesize_answer_minimal(
            self.claude,
            self.synthesis_model,
            self.SYNTHESIS_MAX_TOKENS,
            self._track_response,
            question,
        )

    def _synthesize_answer(
        self,
        question: str,
        kg_results: dict,
        query_plan: dict,
        few_shot_examples: list[dict] | None = None,
    ) -> str:
        """Use Claude to synthesize natural language answer from KG results."""
        from wikigr.agent.synthesizer import synthesize_answer

        return synthesize_answer(
            self.claude,
            self.synthesis_model,
            self.SYNTHESIS_MAX_TOKENS,
            self._track_response,
            self._build_synthesis_context,
            question,
            kg_results,
            query_plan,
            few_shot_examples,
        )

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
        df = self._safe_query(
            """
            MATCH (e:Entity {name: $name})
            OPTIONAL MATCH (a:Article)-[:HAS_ENTITY]->(e)
            RETURN e.name AS name, e.type AS type, e.description AS description,
                   collect(a.title) AS source_articles
            """,
            {"name": entity_name},
            log_context="find_entity",
        )
        if df is None:
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

        # Simplified query without path list comprehensions (LadybugDB limitation)
        df = self._safe_query(
            f"""
            MATCH path = (src:Entity {{name: $src}})-[:ENTITY_RELATION*1..{max_hops}]->(tgt:Entity {{name: $tgt}})
            RETURN src.name AS source, tgt.name AS target, length(path) AS hops
            ORDER BY hops ASC
            LIMIT 5
            """,
            {"src": source_entity, "tgt": target_entity},
            log_context="find_relationship_path",
        )
        if df is None:
            return []

        paths = [
            {
                "source": source,
                "target": target,
                "hops": hops,
                "note": "Full path details require multiple queries in LadybugDB",
            }
            for source, target, hops in zip(
                df["source"].tolist(), df["target"].tolist(), df["hops"].tolist()
            )
        ]

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
        df = self._safe_query(
            """
            MATCH (a:Article {title: $name})-[:HAS_FACT]->(f:Fact)
            RETURN f.content AS fact
            """,
            {"name": entity_or_article},
            log_context="get_entity_facts (article)",
        )
        if df is not None:
            return df["fact"].tolist()

        # Try as entity
        df = self._safe_query(
            """
            MATCH (e:Entity {name: $name})<-[:HAS_ENTITY]-(a:Article)-[:HAS_FACT]->(f:Fact)
            RETURN DISTINCT f.content AS fact
            """,
            {"name": entity_or_article},
            log_context="get_entity_facts (entity)",
        )
        return df["fact"].tolist() if df is not None else []

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
            embeddings = generator.generate_query([query])
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

        # Aggregate by article, keeping best-matching section content.
        # Iterate column lists directly — faster than df.iterrows() which boxes each row.
        articles = {}
        for node, distance in zip(df["node"].tolist(), df["distance"].tolist()):
            section_id = node.get("section_id", "")
            article_title = section_id.split("#")[0]
            content = node.get("content", "")

            if article_title not in articles or distance < articles[article_title]["distance"]:
                articles[article_title] = {
                    "title": article_title,
                    "similarity": max(0.0, min(1.0, 1.0 - distance)),
                    "distance": distance,
                    "content": content or "",
                }

        # Sort by similarity
        results = sorted(articles.values(), key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self) -> None:
        """Close database connection and release embedding model if loaded."""
        self.conn = None  # type: ignore[assignment]
        self.db = None  # type: ignore[assignment]
        self._embedding_generator = None
        self._plan_cache.clear()
