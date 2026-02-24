# Knowledge Packs Design Document

**Status**: Design Proposal
**Created**: 2026-02-24
**Author**: WikiGR Project
**Type**: Explanation (Architecture & Design)

## Executive Summary

### Vision

Knowledge Packs transform domain-specific knowledge graphs into reusable, distributable agent skills. A knowledge pack bundles a curated graph database, specialized retrieval configuration, and skill interface into a single portable unit that enhances AI agents beyond their training data and web search capabilities.

**User Experience:**

```bash
# Install a knowledge pack
wikigr pack install physics-expert

# Claude Code automatically loads the skill
# User: "Explain quantum tunneling using the physics-expert skill"
# Agent uses graph-enhanced retrieval from curated physics knowledge
```

### Core Benefits

1. **Beyond Training Data**: Agents access curated, structured knowledge that exceeds their training cutoff and web search quality
2. **Portable Expertise**: Domain knowledge becomes a distributable artifact (like npm packages or Docker images)
3. **Measurable Enhancement**: Objective evaluation proves when packs outperform baseline capabilities
4. **Zero Configuration**: Packs install to `~/.wikigr/packs/` and auto-register as Claude Code skills
5. **Graph-Enhanced Quality**: Semantic relationships improve context, reduce hallucinations, provide citations

### Success Criteria

A knowledge pack is successful when:

- **Accuracy**: >90% correct answers on domain-specific questions (vs <70% baseline)
- **Hallucination Rate**: <5% fabricated information (vs >15% baseline)
- **Citation Quality**: >95% of answers include verifiable citations
- **Latency**: <2s response time for retrieval queries
- **Coverage**: Handles >80% of common domain questions
- **Adoption**: Users prefer pack over web search for domain tasks

## Architecture Overview

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Claude Code Session                      │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Skill Loader (~/.claude/skills/)                     │  │
│  │  - Auto-discovers packs from ~/.wikigr/packs/        │  │
│  │  - Loads pack skill.md as Claude Code skill          │  │
│  └───────────────────────────────────────────────────────┘  │
│                            │                                 │
│                            ▼                                 │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Knowledge Pack Skill (e.g., physics-expert)          │  │
│  │  - Skill interface with prompt templates             │  │
│  │  - Invokes pack-specific KG Agent                    │  │
│  └───────────────────────────────────────────────────────┘  │
│                            │                                 │
│                            ▼                                 │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  KG Agent Retrieval Engine                            │  │
│  │  - Pack-specific configuration (kg_config.json)       │  │
│  │  - Hybrid search: vector + graph + keyword           │  │
│  │  - Context assembly with citations                    │  │
│  └───────────────────────────────────────────────────────┘  │
│                            │                                 │
│                            ▼                                 │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Kuzu Graph Database (pack.db)                        │  │
│  │  - Domain-specific entities and relationships         │  │
│  │  - Vector embeddings for semantic search             │  │
│  │  - Metadata: provenance, quality scores               │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘

Pack Installation:
~/.wikigr/packs/physics-expert/
├── manifest.json          # Pack metadata & dependencies
├── pack.db                # Kuzu graph database
├── kg_config.json         # KG Agent configuration
├── skill.md               # Claude Code skill interface
├── eval/                  # Evaluation benchmarks
│   ├── questions.jsonl    # Test questions with ground truth
│   └── baselines.json     # Baseline performance metrics
└── README.md              # Pack documentation
```

### Data Flow

1. **User Invokes Skill**: "Use physics-expert to explain quantum tunneling"
2. **Skill Activates**: Claude Code loads `~/.wikigr/packs/physics-expert/skill.md`
3. **Query Formulation**: Skill transforms user request into structured query
4. **Graph Retrieval**: KG Agent searches `pack.db` using hybrid retrieval
5. **Context Assembly**: Retrieved entities, relationships, and sections formatted with citations
6. **Response Generation**: Claude uses graph context to answer with citations
7. **Quality Metrics**: Optional logging for evaluation (accuracy, latency, citations)

### Integration Points

| Component | Integration Method | Configuration |
|-----------|-------------------|---------------|
| **Claude Code Skills** | Auto-discovery from `~/.wikigr/packs/*/skill.md` | Skill frontmatter defines interface |
| **KG Agent** | Python API (`KGAgent` class from `backend/kg_agent.py`) | `kg_config.json` per pack |
| **Kuzu Database** | Direct file access (`pack.db`) | Standard WikiGR schema |
| **Evaluation** | CLI command `wikigr pack eval <pack-name>` | `eval/questions.jsonl` |
| **Distribution** | Tar archive or git repo | `manifest.json` specifies dependencies |

## Pack Manifest Format

### Schema (manifest.json)

```json
{
  "$schema": "https://wikigr.org/schemas/knowledge-pack-v1.json",
  "name": "physics-expert",
  "version": "1.2.0",
  "description": "Expert knowledge in quantum mechanics, relativity, and classical physics",
  "author": "WikiGR Physics Team",
  "license": "CC-BY-SA-4.0",
  "homepage": "https://github.com/wikigr/packs-physics-expert",

  "knowledge_base": {
    "database": "pack.db",
    "schema_version": "wikigr-v1",
    "stats": {
      "articles": 5240,
      "entities": 18500,
      "relationships": 42300,
      "size_mb": 420
    },
    "sources": [
      {
        "name": "Wikipedia Physics Portal",
        "date_extracted": "2026-01-15",
        "article_count": 3200,
        "license": "CC-BY-SA-3.0"
      },
      {
        "name": "arXiv Physics Papers",
        "date_extracted": "2026-01-20",
        "article_count": 2040,
        "license": "CC-BY-4.0"
      }
    ]
  },

  "skill": {
    "interface": "skill.md",
    "activation_keywords": [
      "physics-expert",
      "quantum mechanics",
      "relativity"
    ],
    "kg_config": "kg_config.json"
  },

  "evaluation": {
    "benchmark_dir": "eval/",
    "baseline_scores": {
      "claude_training_data": {
        "accuracy": 0.68,
        "hallucination_rate": 0.18,
        "citation_quality": 0.12
      },
      "web_search": {
        "accuracy": 0.72,
        "hallucination_rate": 0.14,
        "citation_quality": 0.65
      },
      "knowledge_pack": {
        "accuracy": 0.94,
        "hallucination_rate": 0.04,
        "citation_quality": 0.98
      }
    }
  },

  "requirements": {
    "wikigr_version": ">=0.9.0",
    "kuzu_version": ">=0.7.0",
    "disk_space_mb": 450
  },

  "metadata": {
    "created": "2026-01-15T10:30:00Z",
    "updated": "2026-02-20T14:22:00Z",
    "downloads": 1247,
    "rating": 4.8,
    "tags": ["physics", "quantum-mechanics", "relativity", "education"]
  }
}
```

### Versioning Strategy

Knowledge packs follow semantic versioning:

- **Major (1.x.x)**: Breaking schema changes, incompatible database format
- **Minor (x.1.x)**: New content additions, backward-compatible enhancements
- **Patch (x.x.1)**: Bug fixes, metadata corrections, evaluation updates

Example:
- `1.0.0`: Initial physics pack (quantum mechanics only)
- `1.1.0`: Added relativity section (3000 new articles)
- `1.1.1`: Fixed citation formatting in 50 articles
- `2.0.0`: Migrated to Kuzu v0.8 schema (breaking change)

## Skills Integration

### Skill Interface (skill.md)

Each pack provides a `skill.md` file that defines its Claude Code skill interface:

```markdown
---
name: physics-expert
description: Domain expert in physics with graph-enhanced knowledge retrieval
author: WikiGR Physics Team
version: 1.2.0
activation:
  keywords:
    - physics-expert
    - quantum mechanics
    - relativity
    - thermodynamics
  auto_load: false
dependencies:
  - wikigr>=0.9.0
---

# Physics Expert Knowledge Pack

## Purpose

Provides expert-level physics knowledge through graph-enhanced retrieval from 5,240 curated articles covering quantum mechanics, relativity, classical mechanics, thermodynamics, and electromagnetism.

## When I Activate

I load when you:
- Use "physics-expert" skill explicitly
- Ask physics questions with keyword triggers
- Request graph-enhanced physics knowledge

## Capabilities

### 1. Concept Explanations

**Query**: "Explain quantum tunneling"

**What I do**:
1. Search graph for "quantum tunneling" entity
2. Retrieve related concepts (wave-particle duality, uncertainty principle)
3. Find real-world examples (alpha decay, scanning tunneling microscope)
4. Assemble explanation with citations

**Output**: Structured explanation with:
- Core concept definition
- Mathematical foundations
- Physical intuition
- Applications and examples
- Citations to specific articles/sections

### 2. Relationship Discovery

**Query**: "How does quantum mechanics relate to classical mechanics?"

**What I do**:
1. Graph traversal from "quantum mechanics" to "classical mechanics"
2. Find connecting concepts (correspondence principle, limit cases)
3. Identify bridge articles explaining transitions
4. Retrieve historical context

### 3. Problem-Solving Support

**Query**: "Help me solve a particle in a box problem"

**What I do**:
1. Retrieve problem-solving templates from graph
2. Find worked examples with similar boundary conditions
3. Provide step-by-step methodology with citations
4. Suggest related problems for practice

## Configuration

The skill automatically uses `kg_config.json` for retrieval:

```json
{
  "vector_search": {
    "top_k": 10,
    "min_similarity": 0.75
  },
  "graph_traversal": {
    "max_depth": 3,
    "relationship_types": ["RELATES_TO", "EXPLAINS", "DEPENDS_ON"]
  },
  "keyword_search": {
    "enabled": true,
    "boost_factor": 1.2
  }
}
```

## Example Usage

```python
# Invoked automatically by Claude Code skill system
from wikigr.pack_manager import KnowledgePackSkill

skill = KnowledgePackSkill("physics-expert")
result = skill.query("Explain the photoelectric effect")

print(result.answer)
# "The photoelectric effect is the emission of electrons from matter..."
# [Citations: Einstein1905PhotoelectricEffect, Hertz1887Discovery]

print(result.context)
# Retrieved entities: [PhotoelectricEffect, Photon, WorkFunction]
# Relationships: [PhotoelectricEffect-EXPLAINED_BY->QuantumMechanics]
```

## Evaluation Metrics

Current performance (v1.2.0):
- **Accuracy**: 94% on 500 physics questions
- **Hallucination Rate**: 4% (vs 18% without pack)
- **Citation Quality**: 98% verifiable sources
- **Latency**: 1.2s average query time

## Limitations

- **Scope**: Physics only (no chemistry or biology crossover)
- **Depth**: Undergraduate to early graduate level
- **Recency**: Knowledge cutoff January 2026
- **Languages**: English only

## Troubleshooting

**Issue**: Skill not loading
**Solution**: Check `~/.wikigr/packs/physics-expert/` exists and `manifest.json` is valid

**Issue**: Low-quality results
**Solution**: Increase `min_similarity` in `kg_config.json` to 0.85

**Issue**: Missing citations
**Solution**: Enable `citation_mode: "strict"` in KG Agent config
```

### Auto-Discovery Mechanism

Claude Code discovers knowledge pack skills through:

1. **Scan Packs Directory**: At session start, scan `~/.wikigr/packs/*/skill.md`
2. **Parse Frontmatter**: Extract `name`, `description`, `activation.keywords`
3. **Register Skill**: Add to available skills list
4. **Context Matching**: Activate when keywords detected or explicitly invoked
5. **Lazy Loading**: Load pack database only when skill is first used

**Implementation Hook** (in Claude Code session initialization):

```python
# Pseudocode for Claude Code integration
def discover_knowledge_pack_skills():
    packs_dir = Path.home() / ".wikigr" / "packs"
    if not packs_dir.exists():
        return []

    skills = []
    for pack_dir in packs_dir.iterdir():
        skill_file = pack_dir / "skill.md"
        if skill_file.exists():
            skill_meta = parse_skill_frontmatter(skill_file)
            skills.append({
                "name": skill_meta["name"],
                "path": skill_file,
                "keywords": skill_meta["activation"]["keywords"],
                "pack_dir": pack_dir
            })

    return skills
```

## Retrieval Agent Configuration

### KG Agent Config (kg_config.json)

Each pack defines custom KG Agent behavior:

```json
{
  "pack_name": "physics-expert",
  "database_path": "pack.db",

  "retrieval_strategy": {
    "hybrid": {
      "vector_weight": 0.6,
      "graph_weight": 0.3,
      "keyword_weight": 0.1
    },
    "vector_search": {
      "model": "text-embedding-3-small",
      "top_k": 10,
      "min_similarity": 0.75,
      "rerank": true
    },
    "graph_traversal": {
      "enabled": true,
      "max_depth": 3,
      "relationship_types": [
        "RELATES_TO",
        "EXPLAINS",
        "DEPENDS_ON",
        "EXAMPLE_OF",
        "PART_OF"
      ],
      "min_relationship_weight": 0.5
    },
    "keyword_search": {
      "enabled": true,
      "fields": ["title", "content", "entity_name"],
      "boost_exact_match": 1.5,
      "fuzzy_threshold": 0.8
    }
  },

  "context_assembly": {
    "max_sections": 5,
    "max_entities": 15,
    "max_relationships": 20,
    "citation_mode": "strict",
    "include_provenance": true,
    "deduplication": true
  },

  "prompting": {
    "system_prompt_template": "You are a physics domain expert with access to curated knowledge. Always cite sources using [Article:Section] format. Prioritize graph relationships for multi-hop reasoning.",
    "few_shot_examples": [
      {
        "question": "What is quantum entanglement?",
        "retrieved_context": "[Entity: QuantumEntanglement] [Relationship: QuantumEntanglement->RELATED_TO->BellInequality]",
        "answer": "Quantum entanglement is a phenomenon where particles become correlated... [Einstein1935EPRParadox]"
      }
    ],
    "fallback_behavior": "web_search_if_no_results"
  },

  "caching": {
    "enabled": true,
    "ttl_seconds": 3600,
    "max_cache_size_mb": 100
  },

  "monitoring": {
    "log_queries": true,
    "log_path": "~/.wikigr/logs/physics-expert-queries.jsonl",
    "track_metrics": ["latency", "retrieval_count", "citation_count"]
  }
}
```

### KG Agent Integration

Knowledge packs use the existing WikiGR KG Agent with pack-specific configuration:

```python
# backend/pack_kg_agent.py (new file)
from pathlib import Path
import json
from kg_agent import KGAgent

class PackKGAgent:
    """KG Agent wrapper for knowledge packs"""

    def __init__(self, pack_name: str):
        pack_dir = Path.home() / ".wikigr" / "packs" / pack_name
        config_path = pack_dir / "kg_config.json"
        db_path = pack_dir / "pack.db"

        with open(config_path) as f:
            config = json.load(f)

        self.agent = KGAgent(
            db_path=str(db_path),
            config=config
        )
        self.pack_name = pack_name
        self.config = config

    def query(self, question: str, context: dict = None) -> dict:
        """Execute hybrid retrieval query"""
        result = self.agent.hybrid_search(
            query=question,
            top_k=self.config["retrieval_strategy"]["vector_search"]["top_k"],
            include_relationships=True,
            include_citations=True
        )

        return {
            "answer_context": result["sections"],
            "entities": result["entities"],
            "relationships": result["relationships"],
            "citations": result["citations"],
            "metadata": {
                "pack": self.pack_name,
                "retrieval_time_ms": result["latency_ms"],
                "sources": len(result["citations"])
            }
        }

    def explain_concept(self, concept: str) -> dict:
        """Retrieve comprehensive explanation for a concept"""
        # 1. Find concept entity
        entity = self.agent.find_entity(concept)

        # 2. Graph traversal for related concepts
        related = self.agent.traverse_relationships(
            entity_id=entity["id"],
            relationship_types=["RELATES_TO", "EXPLAINS"],
            max_depth=2
        )

        # 3. Retrieve sections mentioning concept
        sections = self.agent.keyword_search(
            query=concept,
            top_k=5
        )

        return {
            "concept": entity,
            "related_concepts": related,
            "explanations": sections,
            "citations": self._format_citations(entity, sections)
        }
```

## Evaluation Framework

### Three-Baseline Comparison

Every knowledge pack must demonstrate superiority over three baselines:

#### Baseline 1: Claude Training Data

**Setup**: Ask Claude questions without any external knowledge access (no web search, no pack).

**Example Evaluation**:

```python
# eval/baselines/training_data.py
def evaluate_training_baseline(questions: list[dict]) -> dict:
    """Evaluate Claude's training data knowledge"""
    results = []

    for q in questions:
        # Pure Claude response (no tools, no web search)
        response = claude.messages.create(
            model="claude-sonnet-4-5",
            messages=[{"role": "user", "content": q["question"]}],
            max_tokens=500
        )

        results.append({
            "question": q["question"],
            "answer": response.content,
            "ground_truth": q["answer"],
            "correct": check_correctness(response.content, q["answer"]),
            "hallucinated": check_hallucination(response.content, q["facts"]),
            "has_citation": False  # Training baseline has no citations
        })

    return {
        "accuracy": sum(r["correct"] for r in results) / len(results),
        "hallucination_rate": sum(r["hallucinated"] for r in results) / len(results),
        "citation_quality": 0.0,  # No citations possible
        "avg_latency_ms": 800
    }
```

#### Baseline 2: Web Search

**Setup**: Ask Claude questions with web search tool enabled (Claude Code's native web search).

**Example Evaluation**:

```python
# eval/baselines/web_search.py
def evaluate_web_search_baseline(questions: list[dict]) -> dict:
    """Evaluate web search-enhanced responses"""
    results = []

    for q in questions:
        # Claude with web search tool
        response = claude.messages.create(
            model="claude-sonnet-4-5",
            messages=[{"role": "user", "content": q["question"]}],
            tools=[web_search_tool],
            max_tokens=500
        )

        citations = extract_citations(response.content)

        results.append({
            "question": q["question"],
            "answer": response.content,
            "ground_truth": q["answer"],
            "correct": check_correctness(response.content, q["answer"]),
            "hallucinated": check_hallucination(response.content, q["facts"]),
            "has_citation": len(citations) > 0,
            "citation_verifiable": verify_citations(citations)
        })

    return {
        "accuracy": sum(r["correct"] for r in results) / len(results),
        "hallucination_rate": sum(r["hallucinated"] for r in results) / len(results),
        "citation_quality": sum(r["citation_verifiable"] for r in results) / len(results),
        "avg_latency_ms": 2500  # Web search is slower
    }
```

#### Baseline 3: Knowledge Pack

**Setup**: Ask Claude questions with knowledge pack skill active.

**Example Evaluation**:

```python
# eval/baselines/knowledge_pack.py
def evaluate_knowledge_pack(pack_name: str, questions: list[dict]) -> dict:
    """Evaluate knowledge pack performance"""
    pack_agent = PackKGAgent(pack_name)
    results = []

    for q in questions:
        # Retrieve context from pack
        context = pack_agent.query(q["question"])

        # Claude with pack context
        prompt = f"""Using the following curated knowledge:

{format_context(context)}

Answer the question: {q["question"]}

Cite sources using [Article:Section] format."""

        response = claude.messages.create(
            model="claude-sonnet-4-5",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500
        )

        citations = extract_citations(response.content)

        results.append({
            "question": q["question"],
            "answer": response.content,
            "ground_truth": q["answer"],
            "correct": check_correctness(response.content, q["answer"]),
            "hallucinated": check_hallucination(response.content, q["facts"]),
            "has_citation": len(citations) > 0,
            "citation_verifiable": verify_pack_citations(citations, pack_agent),
            "retrieval_time_ms": context["metadata"]["retrieval_time_ms"]
        })

    return {
        "accuracy": sum(r["correct"] for r in results) / len(results),
        "hallucination_rate": sum(r["hallucinated"] for r in results) / len(results),
        "citation_quality": sum(r["citation_verifiable"] for r in results) / len(results),
        "avg_latency_ms": sum(r["retrieval_time_ms"] for r in results) / len(results)
    }
```

### Metrics

| Metric | Definition | Measurement | Target |
|--------|-----------|-------------|---------|
| **Accuracy** | % of factually correct answers | Automated fact-checking + human review | >90% |
| **Hallucination Rate** | % of answers with fabricated information | Detection of unverifiable claims | <5% |
| **Citation Quality** | % of citations that are verifiable and relevant | Link checking + relevance scoring | >95% |
| **Latency** | Average response time (retrieval + generation) | Timestamp deltas | <2s |
| **Coverage** | % of domain questions answerable | Test question pool | >80% |
| **Cost** | API costs per 1000 queries | Token usage tracking | <$5 |

### Benchmark Format (eval/questions.jsonl)

```jsonl
{"id": "phys-001", "question": "What is the Heisenberg uncertainty principle?", "answer": "The Heisenberg uncertainty principle states that the position and momentum of a particle cannot both be precisely determined at the same time.", "facts": ["quantum_mechanics", "uncertainty", "position_momentum"], "difficulty": "basic", "category": "quantum_mechanics"}
{"id": "phys-002", "question": "Explain quantum tunneling and give a real-world example", "answer": "Quantum tunneling is a phenomenon where particles pass through energy barriers that classical physics would forbid. Example: Alpha decay in radioactive materials.", "facts": ["quantum_tunneling", "barrier_penetration", "alpha_decay"], "difficulty": "intermediate", "category": "quantum_mechanics"}
{"id": "phys-003", "question": "How does the correspondence principle connect quantum and classical mechanics?", "answer": "The correspondence principle states that quantum mechanical predictions must approach classical results in the limit of large quantum numbers.", "facts": ["correspondence_principle", "classical_limit", "quantum_classical_bridge"], "difficulty": "advanced", "category": "foundations"}
```

### Running Evaluations

```bash
# Evaluate single pack against all baselines
wikigr pack eval physics-expert

# Output:
# Evaluating physics-expert v1.2.0
#
# Baseline 1: Claude Training Data
#   Accuracy: 68%  Hallucination: 18%  Citations: 0%  Latency: 800ms
#
# Baseline 2: Web Search
#   Accuracy: 72%  Hallucination: 14%  Citations: 65%  Latency: 2500ms
#
# Baseline 3: Knowledge Pack
#   Accuracy: 94%  Hallucination: 4%   Citations: 98%  Latency: 1200ms
#
# ✓ Pack outperforms both baselines
# ✓ Accuracy improvement: +26% vs training, +22% vs web search
# ✓ Hallucination reduction: -14% vs training, -10% vs web search

# Compare multiple packs
wikigr pack compare physics-expert chemistry-expert

# Run continuous evaluation (CI integration)
wikigr pack eval physics-expert --mode ci --output results.json
```

## Distribution & Installation

### Pack Distribution Format

Knowledge packs are distributed as compressed archives or git repositories:

**Option 1: Tar Archive**

```bash
# Create pack archive
wikigr pack build physics-expert
# Output: physics-expert-v1.2.0.tar.gz (450 MB)

# Pack contents:
physics-expert-v1.2.0/
├── manifest.json
├── pack.db
├── kg_config.json
├── skill.md
├── eval/
│   ├── questions.jsonl
│   └── baselines.json
└── README.md
```

**Option 2: Git Repository**

```bash
# Clone pack repository
git clone https://github.com/wikigr/packs-physics-expert.git
cd packs-physics-expert

# Repository structure (same as archive)
# pack.db may use Git LFS for large files
```

### Installation

```bash
# Install from archive
wikigr pack install physics-expert-v1.2.0.tar.gz

# Install from URL
wikigr pack install https://packs.wikigr.org/physics-expert/v1.2.0

# Install from registry (future)
wikigr pack install physics-expert@1.2.0

# Installation process:
# 1. Download/extract to /tmp
# 2. Validate manifest.json
# 3. Check disk space requirements
# 4. Verify database integrity (Kuzu validation)
# 5. Copy to ~/.wikigr/packs/physics-expert/
# 6. Register skill with Claude Code
# 7. Run post-install tests

# List installed packs
wikigr pack list
# physics-expert  v1.2.0  420 MB  5,240 articles  (active)
# math-expert     v0.8.1  280 MB  3,100 articles  (active)
```

### Updates

```bash
# Check for updates
wikigr pack update --check
# physics-expert: v1.2.0 -> v1.3.0 available (+500 articles, bug fixes)

# Update single pack
wikigr pack update physics-expert

# Update all packs
wikigr pack update --all

# Version pinning (manifest.json)
{
  "requirements": {
    "wikigr_version": ">=0.9.0,<2.0.0"
  }
}
```

### Registry (Future Enhancement)

```bash
# Search pack registry
wikigr pack search "machine learning"
# ml-fundamentals     v2.1.0  Deep learning, neural networks, optimization
# tensorflow-expert   v1.5.2  TensorFlow API reference and tutorials
# pytorch-guide       v3.0.1  PyTorch patterns and best practices

# Publish pack to registry
wikigr pack publish physics-expert-v1.2.0.tar.gz --registry https://packs.wikigr.org

# Private registry support
wikigr pack config set registry https://internal.company.com/packs
```

## CLI Commands

### pack create

Create new knowledge pack from Wikipedia dump or custom data:

```bash
# Create pack from Wikipedia category
wikigr pack create physics-expert \
  --source wikipedia \
  --categories "Physics" "Quantum_mechanics" "Relativity" \
  --max-articles 5000 \
  --output ./physics-expert

# Create pack from custom articles
wikigr pack create microsoft-fabric-graphql-expert \
  --source custom \
  --articles ./fabric-docs/ \
  --entities ./fabric-entities.json \
  --relationships ./fabric-relationships.json \
  --output ./microsoft-fabric-graphql-expert

# Interactive pack creation wizard
wikigr pack create --interactive

# Creation process:
# 1. Extract/parse source articles
# 2. Generate entities and relationships (NER + link analysis)
# 3. Create vector embeddings (text-embedding-3-small)
# 4. Build Kuzu database (pack.db)
# 5. Generate default kg_config.json
# 6. Create skill.md template
# 7. Generate evaluation question set (optional)
# 8. Package as distributable archive
```

**Output Structure**:

```
physics-expert/
├── manifest.json           # Generated metadata
├── pack.db                 # Kuzu graph database
├── kg_config.json          # Default retrieval config
├── skill.md                # Skill template (user edits)
├── eval/
│   └── questions.jsonl     # Auto-generated test questions
├── README.md               # Pack documentation template
└── sources/
    ├── articles.jsonl      # Original article texts
    └── extraction_log.json # Processing metadata
```

### pack install

Install knowledge pack for use with Claude Code:

```bash
# Install from local file
wikigr pack install ./physics-expert-v1.2.0.tar.gz

# Install from URL
wikigr pack install https://packs.wikigr.org/physics-expert-v1.2.0.tar.gz

# Install with verification
wikigr pack install physics-expert-v1.2.0.tar.gz --verify-checksums

# Dry-run (check without installing)
wikigr pack install physics-expert-v1.2.0.tar.gz --dry-run

# Force reinstall
wikigr pack install physics-expert-v1.2.0.tar.gz --force
```

### pack list

List installed knowledge packs:

```bash
# List all installed packs
wikigr pack list

# Output:
# NAME                     VERSION  SIZE    ARTICLES  STATUS
# physics-expert           v1.2.0   420 MB  5,240     active
# microsoft-fabric-gql     v0.3.1   180 MB  1,850     active
# math-expert              v0.8.1   280 MB  3,100     inactive

# Detailed view
wikigr pack list --detailed

# JSON output for scripting
wikigr pack list --format json
```

### pack info

Show detailed pack information:

```bash
wikigr pack info physics-expert

# Output:
# Knowledge Pack: physics-expert
# Version: 1.2.0
# Author: WikiGR Physics Team
# License: CC-BY-SA-4.0
#
# Database:
#   Articles: 5,240
#   Entities: 18,500
#   Relationships: 42,300
#   Size: 420 MB
#
# Sources:
#   - Wikipedia Physics Portal (3,200 articles, 2026-01-15)
#   - arXiv Physics Papers (2,040 articles, 2026-01-20)
#
# Evaluation (500 questions):
#   Accuracy: 94%
#   Hallucination Rate: 4%
#   Citation Quality: 98%
#
# Installed: 2026-02-20 14:22:00
# Location: ~/.wikigr/packs/physics-expert/
```

### pack eval

Evaluate pack performance against baselines:

```bash
# Run full evaluation
wikigr pack eval physics-expert

# Quick evaluation (subset of questions)
wikigr pack eval physics-expert --quick

# Evaluate specific category
wikigr pack eval physics-expert --category quantum_mechanics

# Compare against specific baseline
wikigr pack eval physics-expert --baseline training_data

# CI mode (JSON output, exit code 1 if targets not met)
wikigr pack eval physics-expert --mode ci --output results.json

# Continuous evaluation (run on schedule)
wikigr pack eval physics-expert --continuous --interval 24h
```

### pack update

Update installed knowledge packs:

```bash
# Check for updates
wikigr pack update --check

# Update specific pack
wikigr pack update physics-expert

# Update all packs
wikigr pack update --all

# Update to specific version
wikigr pack update physics-expert@1.3.0
```

### pack remove

Uninstall knowledge pack:

```bash
# Remove pack
wikigr pack remove physics-expert

# Remove with confirmation
wikigr pack remove physics-expert --confirm

# Keep evaluation data
wikigr pack remove physics-expert --keep-eval
```

### pack validate

Validate pack integrity and configuration:

```bash
# Validate installed pack
wikigr pack validate physics-expert

# Validate pack archive before install
wikigr pack validate physics-expert-v1.2.0.tar.gz

# Checks performed:
# - manifest.json schema compliance
# - pack.db Kuzu database integrity
# - kg_config.json valid configuration
# - skill.md frontmatter parsing
# - eval/questions.jsonl format
# - File checksums (if manifest includes them)
# - Disk space requirements
```

## Implementation Plan

### Phase 1: Core Infrastructure (4 weeks)

**Goal**: Basic pack creation and installation working

**Deliverables**:
1. Pack manifest schema and validation
2. `wikigr pack create` command (Wikipedia source only)
3. `wikigr pack install` command (local files)
4. `~/.wikigr/packs/` directory structure
5. Basic `PackKGAgent` wrapper around existing `KGAgent`

**Dependencies**:
- Existing WikiGR KG Agent (`backend/kg_agent.py`)
- Kuzu database libraries
- Wikipedia data extraction (existing ingestion code)

**Effort Estimate**: 80 hours
- CLI framework: 16h
- Pack creation pipeline: 32h
- Installation logic: 16h
- Testing: 16h

### Phase 2: Skills Integration (3 weeks)

**Goal**: Packs accessible as Claude Code skills

**Deliverables**:
1. `skill.md` template generation
2. Claude Code auto-discovery integration (coordination with Claude team)
3. Pack-specific KG Agent configuration loading
4. Skill activation and query routing
5. Documentation and examples

**Dependencies**:
- Phase 1 complete
- Claude Code skills API (external coordination)

**Effort Estimate**: 60 hours
- Skill template generation: 12h
- Claude Code integration: 24h
- Query routing: 12h
- Documentation: 12h

### Phase 3: Evaluation Framework (3 weeks)

**Goal**: Objective measurement of pack effectiveness

**Deliverables**:
1. Three-baseline evaluation harness
2. Question generation from pack content
3. `wikigr pack eval` command
4. Metrics dashboard (terminal UI)
5. CI integration for continuous evaluation

**Dependencies**:
- Phase 1 & 2 complete
- Claude API for baseline evaluations

**Effort Estimate**: 60 hours
- Evaluation harness: 20h
- Question generation: 12h
- CLI command: 12h
- Dashboard: 8h
- CI integration: 8h

### Phase 4: Distribution & Registry (4 weeks)

**Goal**: Pack sharing and discovery

**Deliverables**:
1. Pack archive creation (`tar.gz` format)
2. `wikigr pack install` from URLs
3. Pack registry prototype (simple file-based)
4. Update mechanism
5. Checksum verification

**Dependencies**:
- Phase 1-3 complete
- Web hosting for registry (optional)

**Effort Estimate**: 80 hours
- Archive creation: 16h
- URL installation: 12h
- Registry backend: 24h
- Update mechanism: 16h
- Security (checksums): 12h

### Phase 5: Advanced Features (6 weeks)

**Goal**: Enhanced capabilities and optimizations

**Deliverables**:
1. Custom data source support (beyond Wikipedia)
2. Pack versioning and migrations
3. Multi-pack queries (cross-domain)
4. Pack analytics (query logs, usage stats)
5. Performance optimizations (caching, indexing)
6. Production-ready examples (physics, Microsoft Fabric GraphQL)

**Dependencies**:
- Phase 1-4 complete

**Effort Estimate**: 120 hours
- Custom sources: 32h
- Versioning: 24h
- Multi-pack queries: 24h
- Analytics: 20h
- Optimizations: 20h

### Timeline Summary

| Phase | Duration | Dependencies | Key Milestone |
|-------|----------|--------------|---------------|
| Phase 1 | 4 weeks | None | Basic pack creation working |
| Phase 2 | 3 weeks | Phase 1 | Packs usable as Claude skills |
| Phase 3 | 3 weeks | Phase 1-2 | Objective evaluation working |
| Phase 4 | 4 weeks | Phase 1-3 | Pack sharing enabled |
| Phase 5 | 6 weeks | Phase 1-4 | Production-ready system |

**Total Timeline**: ~20 weeks (5 months)

**Parallel Workstreams**:
- Phase 2 & 3 can partially overlap (skills integration independent of eval)
- Phase 4 can start once Phase 1 is stable
- Phase 5 features can be incrementally added

## Examples

### Example 1: Physics Expert Pack

**Scenario**: Undergraduate physics student needs help understanding quantum mechanics concepts with reliable citations.

**Pack Creation**:

```bash
# Create physics pack from Wikipedia physics portal
wikigr pack create physics-expert \
  --source wikipedia \
  --categories "Physics" "Quantum_mechanics" "Relativity" "Thermodynamics" \
  --max-articles 5000 \
  --output ./physics-expert

# Processing...
# [1/7] Extracting Wikipedia articles: 5,240 articles (35 min)
# [2/7] Generating entities: 18,500 entities (22 min)
# [3/7] Extracting relationships: 42,300 relationships (18 min)
# [4/7] Creating vector embeddings: 5,240 articles (12 min)
# [5/7] Building Kuzu database: pack.db (8 min)
# [6/7] Generating configuration: kg_config.json, skill.md
# [7/7] Creating evaluation questions: 500 questions
#
# ✓ Pack created: ./physics-expert/ (420 MB)
```

**Installation**:

```bash
wikigr pack install ./physics-expert

# Installing physics-expert v1.0.0
# Validating manifest... ✓
# Checking disk space (450 MB required)... ✓
# Copying database... ✓
# Registering skill... ✓
# Running validation tests... ✓
#
# ✓ physics-expert installed successfully
# Use in Claude Code: "Use physics-expert to explain quantum tunneling"
```

**Usage in Claude Code**:

```
User: "Use physics-expert to explain the Heisenberg uncertainty principle"

Claude: [Activating physics-expert skill]

The Heisenberg uncertainty principle states that certain pairs of physical
properties cannot be simultaneously known to arbitrary precision. The most
common formulation involves position (x) and momentum (p):

Δx · Δp ≥ ℏ/2

where Δx is the uncertainty in position, Δp is the uncertainty in momentum,
and ℏ is the reduced Planck constant.

Physical Intuition:
The principle arises from the wave-particle duality of quantum objects. To
measure position precisely, we must use a short-wavelength probe, which
imparts significant momentum to the particle. Conversely, precise momentum
measurement requires long-wavelength probes that provide poor position
information.

Real-World Implications:
- Atomic stability: Electrons cannot collapse into the nucleus because
  confining them to a small space (small Δx) results in large momentum
  uncertainty, giving them kinetic energy that prevents collapse.
- Scanning tunneling microscopes: Position-momentum trade-offs limit
  simultaneous measurement of electron position and velocity.

Related Concepts:
- Wave-particle duality [QuantumMechanics:WaveParticle]
- Copenhagen interpretation [QuantumMechanics:Copenhagen]
- Quantum measurement problem [QuantumMechanics:Measurement]

Citations:
[Heisenberg1927UncertaintyPaper]
[BohrHeisenbergDebates1928]
[ModernQuantumMechanics:Chapter3:Section2]
```

**Evaluation Results**:

```bash
wikigr pack eval physics-expert

# Evaluating physics-expert v1.0.0 (500 test questions)
#
# Baseline 1: Claude Training Data (no external knowledge)
#   Accuracy: 68.2%  (341/500 correct)
#   Hallucination Rate: 17.8%  (89/500 fabricated facts)
#   Citation Quality: 0.0%  (no citations)
#   Avg Latency: 780ms
#
# Baseline 2: Web Search (Claude with web search tool)
#   Accuracy: 71.6%  (358/500 correct)
#   Hallucination Rate: 13.4%  (67/500 fabricated facts)
#   Citation Quality: 64.2%  (321/500 verifiable citations)
#   Avg Latency: 2,420ms
#
# Baseline 3: Knowledge Pack (physics-expert)
#   Accuracy: 93.8%  (469/500 correct)
#   Hallucination Rate: 4.2%  (21/500 fabricated facts)
#   Citation Quality: 97.6%  (488/500 verifiable citations)
#   Avg Latency: 1,180ms
#
# ✓ Pack significantly outperforms both baselines
# ✓ Accuracy: +25.6% vs training, +22.2% vs web search
# ✓ Hallucination reduction: -13.6% vs training, -9.2% vs web search
# ✓ Citation quality: +97.6% vs training, +33.4% vs web search
# ✓ Latency: 1.5x faster than web search
#
# Breakdown by category:
#   Quantum Mechanics: 96.2% accuracy (125/130)
#   Relativity: 92.4% accuracy (97/105)
#   Thermodynamics: 91.8% accuracy (112/122)
#   Classical Mechanics: 94.6% accuracy (135/143)
```

### Example 2: Microsoft Fabric GraphQL Expert Pack

**Scenario**: Data engineer needs help with Microsoft Fabric Graph Query Language (GQL) with accurate API references and code examples.

**Pack Creation from Custom Docs**:

```bash
# Prepare custom documentation
mkdir fabric-docs
# Copy Microsoft Fabric documentation markdown files
# Include: API reference, tutorials, code examples, architecture docs

# Create entities file (entities.json)
[
  {
    "name": "MATCH Clause",
    "type": "GraphQL_Syntax",
    "description": "Pattern matching in graph queries",
    "properties": {"category": "query_clause", "required": true}
  },
  {
    "name": "CREATE Statement",
    "type": "GraphQL_Syntax",
    "description": "Create new nodes and relationships",
    "properties": {"category": "modification_statement"}
  }
]

# Create relationships file (relationships.json)
[
  {
    "source": "MATCH Clause",
    "target": "WHERE Clause",
    "type": "FOLLOWED_BY",
    "properties": {"optional": true}
  },
  {
    "source": "MATCH Clause",
    "target": "RETURN Clause",
    "type": "FOLLOWED_BY",
    "properties": {"required": true}
  }
]

# Create pack
wikigr pack create microsoft-fabric-graphql-expert \
  --source custom \
  --articles ./fabric-docs/ \
  --entities ./entities.json \
  --relationships ./relationships.json \
  --output ./microsoft-fabric-graphql-expert

# Processing...
# [1/7] Parsing custom articles: 1,850 documents
# [2/7] Loading entities: 4,200 entities
# [3/7] Loading relationships: 8,900 relationships
# [4/7] Creating vector embeddings: 1,850 documents
# [5/7] Building Kuzu database: pack.db
# [6/7] Generating configuration files
# [7/7] Creating evaluation questions: 200 questions
#
# ✓ Pack created: ./microsoft-fabric-graphql-expert/ (180 MB)
```

**skill.md Customization**:

```markdown
---
name: microsoft-fabric-graphql-expert
description: Expert in Microsoft Fabric Graph Query Language (GQL) with API references
author: Microsoft Data Platform Team
version: 0.3.1
activation:
  keywords:
    - microsoft-fabric-graphql-expert
    - fabric gql
    - graph query language
  auto_load: false
---

# Microsoft Fabric GraphQL Expert

## Purpose

Provides authoritative knowledge of Microsoft Fabric's Graph Query Language
(GQL) including syntax, API reference, code examples, and best practices.

## Capabilities

### 1. Syntax Reference

**Query**: "Show me the syntax for MATCH clauses in Fabric GQL"

**Output**: Complete syntax with parameters, examples, and common patterns

### 2. Code Examples

**Query**: "How do I query all nodes with a specific property?"

**Output**: Working code examples with explanations and best practices

### 3. Query Optimization

**Query**: "How can I optimize this graph traversal query?"

**Output**: Performance recommendations with index usage and query rewriting

### 4. API Documentation

**Query**: "What are the parameters for CREATE statement?"

**Output**: Complete API reference with type signatures and examples

## Example Usage

```cypher
-- Query from pack: Find all related entities within 3 hops
MATCH path = (start:Entity {id: $entityId})-[:RELATED_TO*1..3]-(related)
WHERE related.type IN ['Concept', 'Definition']
RETURN path, length(path) as distance
ORDER BY distance ASC
LIMIT 10;

-- Citation: [FabricGQL_API_Reference:MATCH_Clause:Patterns]
```

## Evaluation Metrics

- **Accuracy**: 91% on 200 GQL queries
- **Code Correctness**: 96% of generated queries execute successfully
- **API Coverage**: 100% of documented GQL features
```

**Usage**:

```
User: "Use microsoft-fabric-graphql-expert to write a query that finds
       all warehouses connected to a specific lakehouse"

Claude: [Activating microsoft-fabric-graphql-expert skill]

Here's a Fabric GQL query to find warehouses connected to a lakehouse:

```cypher
MATCH (lh:Lakehouse {name: $lakehouseName})
      -[:CONNECTED_TO|:USES_DATA_FROM]->(wh:Warehouse)
OPTIONAL MATCH (wh)-[:CONTAINS]->(table:Table)
RETURN wh.name AS warehouse_name,
       wh.capacity AS warehouse_capacity,
       collect(table.name) AS table_names,
       count(table) AS table_count
ORDER BY warehouse_name ASC;
```

Explanation:
- **MATCH clause**: Finds the lakehouse by name and follows relationships
  (CONNECTED_TO or USES_DATA_FROM) to warehouses
- **OPTIONAL MATCH**: Includes warehouse tables if they exist (won't filter
  out warehouses with no tables)
- **collect()**: Aggregates table names into an array
- **count()**: Counts related tables

Best Practices:
1. Use parameterized queries ($lakehouseName) for security and performance
2. OPTIONAL MATCH prevents empty results if warehouses have no tables
3. ORDER BY ensures consistent result ordering

Related Patterns:
- Finding reverse dependencies: [FabricGQL_Patterns:ReverseDependency]
- Multi-hop traversals: [FabricGQL_Patterns:GraphTraversal]
- Performance optimization: [FabricGQL_BestPractices:QueryOptimization]

Citations:
[FabricGQL_API_Reference:MATCH_Clause]
[FabricGQL_DataModel:Lakehouse_Warehouse_Relationships]
[FabricGQL_Examples:DataLineageQueries]
```

**Evaluation Results**:

```bash
wikigr pack eval microsoft-fabric-graphql-expert

# Evaluating microsoft-fabric-graphql-expert v0.3.1 (200 test queries)
#
# Baseline 1: Claude Training Data
#   Accuracy: 45.0%  (90/200 correct)  # Limited Fabric GQL in training
#   Code Correctness: 52.5%  (105/200 executable)
#   Hallucination Rate: 34.0%  (68/200 fabricated API features)
#   API Coverage: 62.0%  (124/200 documented features)
#
# Baseline 2: Web Search
#   Accuracy: 68.5%  (137/200 correct)
#   Code Correctness: 74.0%  (148/200 executable)
#   Hallucination Rate: 18.5%  (37/200 fabricated features)
#   API Coverage: 81.0%  (162/200 documented features)
#
# Baseline 3: Knowledge Pack (microsoft-fabric-graphql-expert)
#   Accuracy: 91.0%  (182/200 correct)
#   Code Correctness: 96.0%  (192/200 executable)
#   Hallucination Rate: 3.5%  (7/200 fabricated features)
#   API Coverage: 100.0%  (200/200 documented features)
#
# ✓ Pack significantly outperforms both baselines
# ✓ Accuracy: +46.0% vs training, +22.5% vs web search
# ✓ Code correctness: +43.5% vs training, +22.0% vs web search
# ✓ Hallucination reduction: -30.5% vs training, -15.0% vs web search
# ✓ Complete API coverage (100% of documented features)
#
# Domain-Specific Advantage:
#   Training data limited by recency and coverage of specialized APIs
#   Web search fragmented across multiple unofficial sources
#   Knowledge pack provides canonical, curated reference with graph relationships
```

## Summary

Knowledge Packs represent a paradigm shift in how AI agents access domain-specific knowledge:

1. **Curated Expertise**: Graph databases become reusable, distributable skill modules
2. **Measurable Enhancement**: Objective evaluation proves value over training data and web search
3. **Portable & Shareable**: Pack format enables community-driven knowledge distribution
4. **Graph-Enhanced Quality**: Semantic relationships improve context and reduce hallucinations
5. **Zero Configuration**: Install to `~/.wikigr/packs/` and skills auto-register with Claude Code

**Next Steps**:
1. Implement Phase 1 (core infrastructure) - 4 weeks
2. Build physics-expert proof-of-concept pack
3. Integrate with Claude Code skills system
4. Validate evaluation framework with real-world testing
5. Iterate based on user feedback

**Questions for Discussion**:
- Should packs support multi-language content (beyond English)?
- What pack size limits are acceptable (current: 420 MB for physics)?
- Should we implement pack dependencies (e.g., advanced-physics depends on basic-physics)?
- How to handle pack updates without breaking user workflows?
- Should evaluation be required before pack publication?

---

**Document Metadata**:
- Last Updated: 2026-02-24
- Version: 1.0
- Related: `docs/architecture/kg-agent.md` (when created)
- Status: Design Proposal - Awaiting Review
