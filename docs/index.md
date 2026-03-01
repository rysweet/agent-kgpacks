# Agent Knowledge Packs

**Domain-specific knowledge graph databases that augment LLMs beyond their training data.**

Knowledge Packs are self-contained graph databases built from curated documentation and web content. Each pack bundles a Kuzu graph DB, BGE vector embeddings, and a retrieval pipeline that feeds grounded context into Claude for synthesis. The result: answers that are more accurate, more current, and traceable to specific sources.

---

## The Problem

Large language models have three structural limitations that Knowledge Packs address:

| Limitation | Description | How Packs Help |
|------------|-------------|----------------|
| **Training cutoff** | Models cannot know about APIs, frameworks, or features released after training | Packs ingest current documentation and make it queryable |
| **Depth gaps** | Training covers topics broadly but misses implementation details, edge cases, and advanced patterns | Packs contain full documentation with section-level granularity |
| **Grounding** | Models generate plausible-sounding answers without source attribution | Every pack answer traces back to specific articles and sections |

## Key Metrics

The system has been evaluated across 48 domain-specific packs covering programming languages, frameworks, cloud services, and AI/ML toolkits.

| Condition | Avg Score | Accuracy |
|-----------|-----------|----------|
| **Training** (Claude alone) | 8.9/10 | 96.2% |
| **Pack** (KG Agent, base) | 8.7/10 | 95.0% |
| **Enhanced** (KG Agent + all improvements) | **9.1/10** | **97.5%** |

The Enhanced configuration -- which adds confidence gating, cross-encoder reranking, multi-query retrieval, content quality scoring, graph reranking, multi-document synthesis, and few-shot examples -- beats the training baseline by **+1.3 percentage points** on accuracy across 80 evaluated questions.

---

## Quick Navigation

<div class="grid cards" markdown>

-   **Getting Started**

    New to Knowledge Packs? Start with the [Overview](getting-started/overview.md) to understand what packs are and when to use them, then follow the [Quick Start](getting-started/quickstart.md) to build and query your first pack in 5 minutes.

-   **Concepts**

    Understand [How Packs Work](concepts/how-packs-work.md) under the hood -- from content ingestion through the full [Retrieval Pipeline](concepts/retrieval-pipeline.md) and [Architecture](concepts/architecture.md).

-   **Evaluation**

    Learn the [Methodology](evaluation/methodology.md) behind the three-condition evaluation framework, review current [Results](evaluation/results.md) across all packs, and discover strategies for [Improving Accuracy](evaluation/improving-accuracy.md).

-   **How-To Guides**

    Step-by-step instructions to [Build a Pack](howto/build-a-pack.md), [Run Evaluations](howto/run-evaluations.md), and [Configure Enhancements](howto/configure-enhancements.md).

-   **Reference**

    Complete technical reference for the [KG Agent API](reference/kg-agent-api.md), [CLI Commands](reference/cli-commands.md), and [Pack Manifest](reference/pack-manifest.md) format.

</div>

---

## Project Structure

```
agent-kgpacks/
├── wikigr/                 # Python package (CLI + agents)
│   ├── cli.py              # wikigr pack create / install / eval / ...
│   └── agent/
│       ├── kg_agent.py     # KnowledgeGraphAgent - core query engine
│       ├── reranker.py     # GraphReranker (PageRank-based)
│       ├── multi_doc_synthesis.py  # MultiDocSynthesizer
│       ├── few_shot.py     # FewShotManager
│       └── cross_encoder.py # CrossEncoderReranker
├── scripts/                # Build and evaluation scripts
│   ├── build_*_pack.py     # Per-pack build scripts (48 packs)
│   ├── eval_single_pack.py # Single-pack evaluation
│   └── run_all_packs_evaluation.py  # Cross-pack evaluation
├── data/packs/             # Pack databases and evaluation data
│   ├── go-expert/          # Example pack
│   │   ├── pack.db/        # Kuzu graph database
│   │   ├── manifest.json   # Pack metadata
│   │   ├── urls.txt        # Source URLs
│   │   └── eval/           # Evaluation questions and results
│   └── all_packs_evaluation.json  # Cross-pack results
└── docs/                   # This documentation site
```
