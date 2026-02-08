# WikiGR Implementation Roadmap

**Project:** Wikipedia Knowledge Graph (WikiGR)
**Timeline:** 6 weeks (4-5 weeks implementation + 1 week validation)
**Target:** 30K articles with semantic search and graph traversal

---

## Overview

This roadmap breaks down the implementation into **4 phases** over **6 weeks**:

1. **Foundation (Weeks 1-2):** Core infrastructure, 10 articles
2. **Orchestrator (Week 3):** Expansion logic, 100 articles
3. **Expansion (Week 4):** Link discovery and BFS, 1K articles
4. **Scale & Validation (Weeks 5-6):** 30K articles, testing, optimization

---

## Phase Breakdown

### Phase 1: Foundation (Weeks 1-2) - 40-60 hours

**Goal:** Build core pipeline, validate with 10 articles

**Milestone:** `v0.1-foundation`

#### Issues to Create:

**#2: Set up project structure and dependencies**
- **Effort:** 2 hours
- **Priority:** P0 (Critical)
- **Dependencies:** None
- **Acceptance Criteria:**
  - [ ] Virtual environment created
  - [ ] Dependencies installed (kuzu, sentence-transformers, requests, pandas)
  - [ ] Directory structure complete
  - [ ] requirements.txt documented
  - [ ] README.md with setup instructions
- **Labels:** `setup`, `documentation`

**#3: Implement Kuzu schema (Article, Section, Category nodes)**
- **Effort:** 4 hours
- **Priority:** P0 (Critical)
- **Dependencies:** #2
- **Acceptance Criteria:**
  - [ ] Schema script: `bootstrap/schema/ryugraph_schema.py`
  - [ ] Article node (title, category, word_count, expansion_state, expansion_depth)
  - [ ] Section node (title, content, embedding DOUBLE[384])
  - [ ] Category node (name)
  - [ ] Relationships: HAS_SECTION, LINKS_TO, IN_CATEGORY
  - [ ] Vector index created on Section.embedding
  - [ ] Test: Create sample nodes and verify
- **Labels:** `database`, `schema`

**#4: Implement Wikipedia API client**
- **Effort:** 8 hours
- **Priority:** P0 (Critical)
- **Dependencies:** #2
- **Acceptance Criteria:**
  - [ ] File: `bootstrap/src/wikipedia/api_client.py`
  - [ ] Fetch article using Action API (Parse)
  - [ ] Extract wikitext, links, categories, sections
  - [ ] Parse sections from wikitext (H2/H3)
  - [ ] Rate limiting (100ms delay between requests)
  - [ ] Error handling (404, 500, timeout)
  - [ ] Retry logic with exponential backoff
  - [ ] User-Agent header included
  - [ ] Test: Fetch "Machine Learning" and validate structure
- **Labels:** `api`, `wikipedia`

**#5: Implement section parser (wikitext → sections)**
- **Effort:** 6 hours
- **Priority:** P0 (Critical)
- **Dependencies:** #4
- **Acceptance Criteria:**
  - [ ] File: `bootstrap/src/wikipedia/parser.py`
  - [ ] Extract H2 (== Title ==) and H3 (=== Title ===) sections
  - [ ] Strip wikitext formatting (links, templates, references)
  - [ ] Extract section content (text between headings)
  - [ ] Filter out short sections (<100 chars)
  - [ ] Return structured list: [{level, title, content}]
  - [ ] Test: Parse "Machine Learning" article, verify 10+ sections
- **Labels:** `parsing`, `wikipedia`

**#6: Implement embedding generator**
- **Effort:** 4 hours
- **Priority:** P0 (Critical)
- **Dependencies:** #2
- **Acceptance Criteria:**
  - [ ] File: `bootstrap/src/embeddings/generator.py`
  - [ ] Load paraphrase-MiniLM-L3-v2 model
  - [ ] Generate embeddings in batches (batch_size=32)
  - [ ] Return numpy arrays (N, 384)
  - [ ] GPU support (if available)
  - [ ] Progress bar for large batches
  - [ ] Test: Generate embeddings for 100 texts, verify shape
- **Labels:** `embeddings`, `ml`

**#7: Implement database loader (insert articles into Kuzu)**
- **Effort:** 8 hours
- **Priority:** P0 (Critical)
- **Dependencies:** #3, #4, #5, #6
- **Acceptance Criteria:**
  - [ ] File: `bootstrap/src/database/loader.py`
  - [ ] Insert Article node
  - [ ] Insert Section nodes with embeddings
  - [ ] Insert Category node
  - [ ] Create HAS_SECTION relationships
  - [ ] Create IN_CATEGORY relationships
  - [ ] Batch insertion for efficiency
  - [ ] Transaction handling (rollback on error)
  - [ ] Test: Load 3 articles, verify in database
- **Labels:** `database`, `loader`

**#8: Implement semantic search query**
- **Effort:** 4 hours
- **Priority:** P0 (Critical)
- **Dependencies:** #7
- **Acceptance Criteria:**
  - [ ] File: `bootstrap/src/query/search.py`
  - [ ] Function: `semantic_search(conn, query_title, top_k=10)`
  - [ ] Use QUERY_VECTOR_INDEX to find similar sections
  - [ ] Join to get Article titles
  - [ ] Return list of (article_title, section_title, similarity)
  - [ ] Test: Query "machine learning", verify results
- **Labels:** `query`, `semantic-search`

**#9: End-to-end test with 10 articles**
- **Effort:** 4 hours
- **Priority:** P0 (Critical)
- **Dependencies:** #2-#8
- **Acceptance Criteria:**
  - [ ] Script: `bootstrap/scripts/load_articles.py`
  - [ ] Load 10 articles (diverse topics)
  - [ ] Verify database size (<50 MB)
  - [ ] Run 5 semantic search queries
  - [ ] Measure query latency (avg, p95)
  - [ ] Document results in `bootstrap/docs/10-article-test.md`
  - [ ] Success: P95 latency <500ms, relevance >60%
- **Labels:** `testing`, `milestone`

---

### Phase 2: Orchestrator (Week 3) - 30-40 hours

**Goal:** Build expansion orchestrator, validate with 100 articles

**Milestone:** `v0.2-orchestrator`

#### Issues to Create:

**#10: Design expansion state machine**
- **Effort:** 4 hours
- **Priority:** P0 (Critical)
- **Dependencies:** #9
- **Acceptance Criteria:**
  - [ ] Document state transitions: discovered → claimed → loaded → processed
  - [ ] Define state fields: expansion_state, expansion_depth, claimed_at, processed_at
  - [ ] Define failure states: failed, max_retries_exceeded
  - [ ] Heartbeat mechanism for claim timeouts
  - [ ] Document in `bootstrap/docs/state-machine.md`
- **Labels:** `design`, `orchestrator`

**#11: Implement work queue manager**
- **Effort:** 8 hours
- **Priority:** P0 (Critical)
- **Dependencies:** #10
- **Acceptance Criteria:**
  - [ ] File: `bootstrap/src/expansion/work_queue.py`
  - [ ] Function: `claim_work(batch_size, timeout_seconds)`
  - [ ] Claim oldest unclaimed articles (UPDATE SET claimed_at, state='claimed')
  - [ ] Return list of article titles
  - [ ] Implement heartbeat: `update_heartbeat(article_id)`
  - [ ] Implement reclaim: `reclaim_stale(timeout_seconds)` (reset claimed → discovered)
  - [ ] Test: Claim 10 articles, verify state changes
- **Labels:** `orchestrator`, `work-queue`

**#12: Implement article processor**
- **Effort:** 8 hours
- **Priority:** P0 (Critical)
- **Dependencies:** #11, #7
- **Acceptance Criteria:**
  - [ ] File: `bootstrap/src/expansion/processor.py`
  - [ ] Function: `process_article(title, depth)`
  - [ ] Fetch article from Wikipedia
  - [ ] Parse sections
  - [ ] Generate embeddings
  - [ ] Load into database
  - [ ] Update state: claimed → loaded
  - [ ] Extract links (for future expansion)
  - [ ] Return (success, links, error)
  - [ ] Test: Process "Quantum Computing", verify loaded
- **Labels:** `orchestrator`, `processor`

**#13: Implement expansion orchestrator**
- **Effort:** 10 hours
- **Priority:** P0 (Critical)
- **Dependencies:** #11, #12
- **Acceptance Criteria:**
  - [ ] File: `bootstrap/src/expansion/orchestrator.py`
  - [ ] Class: `RyuGraphOrchestrator(db_path)`
  - [ ] Function: `initialize_seeds(seed_titles)` (insert as discovered, depth=0)
  - [ ] Function: `expand_to_target(target_count)`
  - [ ] Loop: claim work → process → advance state → discover links
  - [ ] Function: `_discover_links(source_id, links, current_depth)`
  - [ ] Function: `_advance_state(article_id, new_state)`
  - [ ] Function: `_handle_failure(article_id, error)`
  - [ ] Progress logging (every 10 articles)
  - [ ] Test: Initialize 5 seeds, expand to 20 articles
- **Labels:** `orchestrator`, `expansion`

**#14: Implement link discovery**
- **Effort:** 6 hours
- **Priority:** P1 (High)
- **Dependencies:** #13
- **Acceptance Criteria:**
  - [ ] File: `bootstrap/src/expansion/link_discovery.py`
  - [ ] Function: `discover_links(source_title, links, current_depth, max_depth)`
  - [ ] Filter links (only main namespace, no special pages)
  - [ ] Check if link already in database (skip if loaded/claimed)
  - [ ] Insert new links as discovered (depth = current_depth + 1)
  - [ ] Create LINKS_TO relationship
  - [ ] Limit per article (e.g., top 50 links)
  - [ ] Test: Discover links from "Machine Learning", verify inserted
- **Labels:** `expansion`, `links`

**#15: End-to-end test with 100 articles**
- **Effort:** 4 hours
- **Priority:** P0 (Critical)
- **Dependencies:** #10-#14
- **Acceptance Criteria:**
  - [ ] Initialize 10 seeds (diverse topics)
  - [ ] Expand to 100 articles total
  - [ ] Measure expansion time
  - [ ] Verify database size (<500 MB)
  - [ ] Run 10 semantic search queries
  - [ ] Measure query latency
  - [ ] Document results in `bootstrap/docs/100-article-test.md`
  - [ ] Success: Expansion completes, P95 latency <500ms
- **Labels:** `testing`, `milestone`

---

### Phase 3: Expansion & Scale (Week 4) - 30-40 hours

**Goal:** Implement BFS expansion strategy, scale to 1K articles

**Milestone:** `v0.3-expansion`

#### Issues to Create:

**#16: Implement radial expansion strategy (BFS)**
- **Effort:** 8 hours
- **Priority:** P1 (High)
- **Dependencies:** #15
- **Acceptance Criteria:**
  - [ ] File: `bootstrap/src/expansion/strategies.py`
  - [ ] Strategy: Breadth-First Search (BFS)
  - [ ] Expand depth-by-depth (all depth=0, then depth=1, then depth=2)
  - [ ] Limit max depth (e.g., 2 hops from seeds)
  - [ ] Category filtering: prefer articles in same category as seeds
  - [ ] Document strategy in `bootstrap/docs/expansion-strategy.md`
  - [ ] Test: Expand 5 seeds with BFS, verify depth distribution
- **Labels:** `expansion`, `strategy`

**#17: Implement monitoring dashboard**
- **Effort:** 8 hours
- **Priority:** P1 (High)
- **Dependencies:** #13
- **Acceptance Criteria:**
  - [ ] File: `bootstrap/scripts/monitor_expansion.py`
  - [ ] Display: state distribution (discovered, claimed, loaded, failed)
  - [ ] Display: expansion progress (% complete)
  - [ ] Display: depth distribution (how many at each depth)
  - [ ] Display: articles per category
  - [ ] Refresh every 30 seconds
  - [ ] Test: Run during expansion, verify real-time updates
- **Labels:** `monitoring`, `dashboard`

**#18: Add error recovery and retry logic**
- **Effort:** 6 hours
- **Priority:** P1 (High)
- **Dependencies:** #13
- **Acceptance Criteria:**
  - [ ] Retry failed articles (max 3 retries)
  - [ ] Exponential backoff for Wikipedia API errors
  - [ ] Handle network timeouts gracefully
  - [ ] Log all failures to `logs/failures.log`
  - [ ] Mark articles as failed after max retries
  - [ ] Continue expansion despite failures
  - [ ] Test: Simulate API failure, verify retry
- **Labels:** `error-handling`, `reliability`

**#19: Optimize batch operations**
- **Effort:** 6 hours
- **Priority:** P2 (Medium)
- **Dependencies:** #7
- **Acceptance Criteria:**
  - [ ] Batch embedding generation (32 sections at a time)
  - [ ] Batch database inserts (10 articles at a time)
  - [ ] Parallel Wikipedia API calls (5 concurrent)
  - [ ] Connection pooling for database
  - [ ] Measure speedup vs sequential
  - [ ] Test: Load 50 articles, compare times
- **Labels:** `optimization`, `performance`

**#20: End-to-end test with 1K articles**
- **Effort:** 4 hours
- **Priority:** P0 (Critical)
- **Dependencies:** #16-#19
- **Acceptance Criteria:**
  - [ ] Initialize 100 seeds (diverse, high-quality)
  - [ ] Expand to 1K articles using BFS strategy
  - [ ] Measure total expansion time
  - [ ] Verify database size (<5 GB)
  - [ ] Run 20 test queries (semantic, graph, hybrid)
  - [ ] Measure query latency (P50, P95, P99)
  - [ ] Calculate semantic search precision
  - [ ] Document results in `bootstrap/docs/1k-article-test.md`
  - [ ] Success: Time <2 hours, P95 latency <500ms, precision >65%
- **Labels:** `testing`, `milestone`

---

### Phase 4: Scale & Validation (Weeks 5-6) - 40-60 hours

**Goal:** Scale to 30K articles, validate performance and quality

**Milestone:** `v1.0-production`

#### Issues to Create:

**#21: Collect 3K seed articles**
- **Effort:** 4 hours
- **Priority:** P0 (Critical)
- **Dependencies:** #20
- **Acceptance Criteria:**
  - [ ] Select 5-6 diverse topic categories
  - [ ] Sample 500-600 articles per category (total 3K)
  - [ ] Validate article quality (complete, well-linked)
  - [ ] Save to `bootstrap/data/seeds.json`
  - [ ] Document selection criteria
  - [ ] Test: Load seeds, verify database contains 3K articles
- **Labels:** `data`, `seeds`

**#22: Expand to 30K articles**
- **Effort:** 8 hours (mostly waiting)
- **Priority:** P0 (Critical)
- **Dependencies:** #21
- **Acceptance Criteria:**
  - [ ] Initialize 3K seeds
  - [ ] Run expansion to 30K articles
  - [ ] Monitor progress with dashboard
  - [ ] Log expansion metrics (time, failures, state distribution)
  - [ ] Verify database size (<10 GB)
  - [ ] Document expansion in `bootstrap/docs/30k-expansion-log.md`
  - [ ] Success: 30K articles loaded, <5% failure rate
- **Labels:** `scale`, `milestone`

**#23: Performance testing (query latency)**
- **Effort:** 6 hours
- **Priority:** P0 (Critical)
- **Dependencies:** #22
- **Acceptance Criteria:**
  - [ ] Run 100 semantic search queries
  - [ ] Measure latency distribution (P50, P95, P99)
  - [ ] Test query performance across different categories
  - [ ] Identify slow queries (>1s)
  - [ ] Document results in `bootstrap/docs/performance-test.md`
  - [ ] Success: P95 latency <500ms
- **Labels:** `testing`, `performance`

**#24: Quality testing (semantic search precision)**
- **Effort:** 8 hours
- **Priority:** P0 (Critical)
- **Dependencies:** #22
- **Acceptance Criteria:**
  - [ ] Define 20 test queries with expected results
  - [ ] Run each query, collect top 10 results
  - [ ] Manually evaluate relevance (binary: relevant/not relevant)
  - [ ] Calculate precision@10 for each query
  - [ ] Calculate average precision across all queries
  - [ ] Document results in `bootstrap/docs/quality-test.md`
  - [ ] Success: Average precision >70%
- **Labels:** `testing`, `quality`

**#25: Implement graph traversal queries**
- **Effort:** 6 hours
- **Priority:** P1 (High)
- **Dependencies:** #22
- **Acceptance Criteria:**
  - [ ] Function: `graph_traversal(conn, seed_title, max_hops=2)`
  - [ ] Use Cypher MATCH with variable-length paths
  - [ ] Return articles within N hops
  - [ ] Filter by category (optional)
  - [ ] Test: Traverse from "Machine Learning" (2 hops)
  - [ ] Verify results include expected neighbors
- **Labels:** `query`, `graph`

**#26: Implement hybrid query (semantic + graph)**
- **Effort:** 6 hours
- **Priority:** P1 (High)
- **Dependencies:** #25, #8
- **Acceptance Criteria:**
  - [ ] Function: `hybrid_query(conn, seed_title, category_filter=None)`
  - [ ] Step 1: Semantic search (top 100)
  - [ ] Step 2: Filter by graph proximity (within 2 hops)
  - [ ] Step 3: Rank by combined score (semantic + graph distance)
  - [ ] Return top 10 results
  - [ ] Test: Hybrid query for "Deep Learning" in CS category
- **Labels:** `query`, `hybrid`

**#27: Memory profiling and optimization**
- **Effort:** 6 hours
- **Priority:** P2 (Medium)
- **Dependencies:** #22
- **Acceptance Criteria:**
  - [ ] Profile memory usage during expansion
  - [ ] Profile memory usage during queries
  - [ ] Identify memory leaks (if any)
  - [ ] Optimize large batch operations
  - [ ] Document memory usage in `bootstrap/docs/memory-profile.md`
  - [ ] Success: Memory usage <500 MB during queries
- **Labels:** `optimization`, `profiling`

**#28: Production hardening**
- **Effort:** 8 hours
- **Priority:** P1 (High)
- **Dependencies:** #22-#27
- **Acceptance Criteria:**
  - [ ] Add comprehensive logging (INFO, ERROR levels)
  - [ ] Add input validation (article titles, parameters)
  - [ ] Add database backup/restore scripts
  - [ ] Add graceful shutdown (handle SIGINT/SIGTERM)
  - [ ] Add configuration file (config.yaml)
  - [ ] Add CLI interface for common operations
  - [ ] Test: Run expansion, interrupt, resume
- **Labels:** `production`, `hardening`

**#29: Final validation and documentation**
- **Effort:** 8 hours
- **Priority:** P0 (Critical)
- **Dependencies:** #21-#28
- **Acceptance Criteria:**
  - [ ] All success criteria met (from issue #1)
  - [ ] Complete README.md with usage instructions
  - [ ] Complete API documentation
  - [ ] Complete architecture documentation
  - [ ] Document known limitations
  - [ ] Document future improvements
  - [ ] Create demo video or screenshots
  - [ ] Tag release: `v1.0`
- **Labels:** `documentation`, `release`

---

## Summary

### Total Effort Estimate

| Phase | Duration | Effort | Issues |
|-------|----------|--------|--------|
| **Phase 1: Foundation** | Weeks 1-2 | 40-60 hours | #2-#9 (8 issues) |
| **Phase 2: Orchestrator** | Week 3 | 30-40 hours | #10-#15 (6 issues) |
| **Phase 3: Expansion** | Week 4 | 30-40 hours | #16-#20 (5 issues) |
| **Phase 4: Scale & Validation** | Weeks 5-6 | 40-60 hours | #21-#29 (9 issues) |
| **Total** | **6 weeks** | **140-200 hours** | **28 issues** |

### Milestones

| Milestone | Target Date | Deliverable |
|-----------|-------------|-------------|
| `v0.1-foundation` | End of Week 2 | 10 articles loaded, semantic search working |
| `v0.2-orchestrator` | End of Week 3 | 100 articles, expansion orchestrator complete |
| `v0.3-expansion` | End of Week 4 | 1K articles, BFS strategy working |
| `v1.0-production` | End of Week 6 | 30K articles, all success criteria met |

### Success Criteria (v1.0)

- [x] 30K articles loaded
- [x] P95 query latency <500ms
- [x] Semantic search precision >70%
- [x] Database size <10 GB
- [x] Memory usage <500 MB
- [x] Failure rate <5%
- [x] Complete documentation

---

## Risk Mitigation

### Risk: Quality Below 70%

**Mitigation:**
- Issue #24: Test quality early (after 1K articles)
- If precision <65%, upgrade to all-MiniLM-L6-v2 (5-10% boost)
- If still insufficient, upgrade to all-mpnet-base-v2 (10-20% boost)

### Risk: Performance Below Target

**Mitigation:**
- Issue #23: Profile queries, identify bottlenecks
- Issue #27: Memory profiling
- Tune HNSW parameters (mu, ml, efc)
- Add Redis caching layer (optional)

### Risk: Expansion Takes Too Long

**Mitigation:**
- Issue #19: Optimize batch operations
- Use GPU for embeddings (10-20x speedup)
- Parallel processing (5 workers)
- Reduce target to 10K articles if needed

---

## Next Steps

1. Create all 28 GitHub issues using this roadmap
2. Assign priorities and labels
3. Set up milestones in GitHub
4. Begin Phase 1 (#2-#9)

**Ready to create GitHub issues?**
