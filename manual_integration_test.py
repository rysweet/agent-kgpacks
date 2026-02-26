#!/usr/bin/env python3
"""Manual integration test for Phase 1 Enhancements.

Tests all three enhancement modules work together:
1. GraphReranker - Reranks results by centrality
2. MultiDocSynthesizer - Expands to related articles
3. FewShotManager - Retrieves similar examples

Uses test_10_articles.db for realistic testing.
"""

import sys
from pathlib import Path

# Ensure wikigr is importable
sys.path.insert(0, str(Path(__file__).parent))

import kuzu

from wikigr.agent.few_shot import FewShotManager
from wikigr.agent.multi_doc_synthesis import MultiDocSynthesizer
from wikigr.agent.reranker import GraphReranker


def test_graph_reranker():
    """Test 1: GraphReranker with test database."""
    print("=" * 70)
    print("TEST 1: GraphReranker")
    print("=" * 70)

    db = kuzu.Database("tests/data/test_10_articles.db", read_only=True)
    conn = kuzu.Connection(db)
    reranker = GraphReranker(conn)

    # Simulate search results
    candidates = [
        {"article_id": 1, "title": "Article 1", "score": 0.9},
        {"article_id": 2, "title": "Article 2", "score": 0.85},
        {"article_id": 3, "title": "Article 3", "score": 0.8},
    ]

    # Rerank with graph centrality
    reranked = reranker.rerank(candidates, vector_weight=0.6, graph_weight=0.4)

    print(f"✓ Reranked {len(candidates)} candidates")
    print(f"  Input order: {[c['title'] for c in candidates]}")
    print(f"  Reranked order: {[r['title'] for r in reranked]}")
    print(
        f"  Top result: {reranked[0]['title']} (combined_score: {reranked[0]['combined_score']:.3f})"
    )
    print()

    return True


def test_multi_doc_synthesizer():
    """Test 2: MultiDocSynthesizer with test database."""
    print("=" * 70)
    print("TEST 2: MultiDocSynthesizer")
    print("=" * 70)

    db = kuzu.Database("tests/data/test_10_articles.db", read_only=True)
    conn = kuzu.Connection(db)
    synthesizer = MultiDocSynthesizer(conn)

    # Expand from seed article
    seed_ids = [1]
    expanded = synthesizer.expand_to_related_articles(seed_ids, max_hops=1, max_articles=5)

    print(f"✓ Expanded from seed {seed_ids} to {len(expanded)} articles")
    print(f"  Articles found: {list(expanded.keys())}")

    # Synthesize with citations
    if expanded:
        citations = synthesizer.synthesize_with_citations(expanded, "test query")
        print(f"✓ Generated citations ({len(citations)} chars)")
        print(f"  Preview: {citations[:200]}...")

    print()
    return True


def test_few_shot_manager():
    """Test 3: FewShotManager with real examples."""
    print("=" * 70)
    print("TEST 3: FewShotManager")
    print("=" * 70)

    manager = FewShotManager("data/few_shot/physics_examples.json")

    print(f"✓ Loaded {len(manager.examples)} examples")

    # Find similar examples
    query = "What is quantum mechanics?"
    examples = manager.find_similar_examples(query, k=2)

    print(f"✓ Found {len(examples)} similar examples for query: '{query}'")
    for i, ex in enumerate(examples, 1):
        print(f"  {i}. {ex['question'][:60]}... (score: {ex['score']:.3f})")

    print()
    return True


def test_integration():
    """Test 4: All enhancements together (integration test)."""
    print("=" * 70)
    print("TEST 4: Full Integration")
    print("=" * 70)

    from wikigr.agent.kg_agent import KnowledgeGraphAgent

    # Test with enhancements disabled (baseline)
    print("Testing baseline (use_enhancements=False)...")
    agent_baseline = KnowledgeGraphAgent(
        "tests/data/test_10_articles.db", read_only=True, use_enhancements=False
    )
    print("✓ Baseline agent initialized")
    print(f"  Enhancements: {agent_baseline.use_enhancements}")
    print(f"  Reranker: {agent_baseline.reranker}")
    print()

    # Test with enhancements enabled
    print("Testing enhanced (use_enhancements=True)...")
    agent_enhanced = KnowledgeGraphAgent(
        "tests/data/test_10_articles.db", read_only=True, use_enhancements=True
    )
    print("✓ Enhanced agent initialized")
    print(f"  Enhancements: {agent_enhanced.use_enhancements}")
    print(f"  Reranker: {type(agent_enhanced.reranker).__name__}")
    print(f"  Synthesizer: {type(agent_enhanced.synthesizer).__name__}")
    print(f"  FewShot: {type(agent_enhanced.few_shot).__name__}")
    print()

    return True


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("PHASE 1 ENHANCEMENTS - MANUAL INTEGRATION TEST")
    print("=" * 70)
    print()

    tests = [
        ("GraphReranker", test_graph_reranker),
        ("MultiDocSynthesizer", test_multi_doc_synthesizer),
        ("FewShotManager", test_few_shot_manager),
        ("Full Integration", test_integration),
    ]

    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, "✅ PASS" if success else "❌ FAIL"))
        except Exception as e:
            print(f"❌ {name} FAILED: {e}")
            results.append((name, f"❌ FAIL: {e}"))
            import traceback

            traceback.print_exc()

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for name, result in results:
        print(f"  {result}: {name}")

    passed = sum(1 for _, r in results if "PASS" in r)
    print(f"\nResult: {passed}/{len(tests)} tests passed")

    sys.exit(0 if passed == len(tests) else 1)
