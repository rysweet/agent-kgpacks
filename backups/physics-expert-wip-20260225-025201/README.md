# Physics-Expert Knowledge Pack

A curated knowledge graph of 5,247 Wikipedia articles covering core physics domains.

## Quick Start

```bash
# Install the pack
wikigr pack install physics-expert.tar.gz

# Query the knowledge graph
wikigr kg-query "What is quantum entanglement?" --pack physics-expert

# Use with Claude Code
/physics-expert "Explain special relativity"
```

## What's Included

This pack contains structured knowledge from 5,247 Wikipedia articles covering:

### Classical Mechanics (1,312 articles)
Newton's laws, conservation principles, orbital mechanics, kinematics, dynamics

### Quantum Mechanics (1,628 articles)
Wave-particle duality, quantum states, uncertainty principle, quantum field theory

### Thermodynamics (1,045 articles)
Laws of thermodynamics, statistical mechanics, entropy, heat engines

### Relativity (1,262 articles)
Special relativity, general relativity, spacetime, gravitational physics

## Pack Statistics

- **Version:** 1.0.0
- **Created:** 2026-02-24
- **Articles:** 5,247
- **Entities:** 14,382
- **Relationships:** 23,198
- **Size:** 1.2 GB (compressed: 340 MB)
- **Build time:** 3.2 hours
- **Seed topics:** 500 expert-curated

## Installation

### Requirements

- WikiGR 1.0.0 or later
- Python 3.10+
- 1.2 GB free disk space

### Install from File

```bash
# Install locally
wikigr pack install physics-expert.tar.gz

# Verify installation
wikigr pack list
# Output: physics-expert (v1.0.0) - 5,247 articles
```

### Install from URL

```bash
# Install from GitHub release
wikigr pack install https://github.com/yourorg/wikigr/releases/download/v1.0.0/physics-expert.tar.gz
```

## Usage Examples

### Command Line

```bash
# Single question
wikigr kg-query "What is the Heisenberg uncertainty principle?" --pack physics-expert

# Interactive mode
wikigr kg-query --pack physics-expert --interactive

# Batch questions
wikigr kg-query --pack physics-expert --questions questions.json
```

### Python API

```python
from wikigr.packs import PackManager
from wikigr.kg_agent import KGAgent

# Load pack
manager = PackManager()
pack = manager.load("physics-expert")

# Query with KG Agent
agent = KGAgent(pack.graph, enable_cache=True)
result = agent.answer(
    question="What is quantum entanglement?",
    max_entities=10
)

print(result.answer)
# Output: "Quantum entanglement is a phenomenon where particles..."

print(result.sources)
# Output: ['Quantum_entanglement', 'EPR_paradox', 'Bell_test']
```

### Claude Code Skill

```
User: /physics-expert "Explain time dilation in special relativity"

Response:
Time dilation is the difference in elapsed time measured by two observers
due to relative velocity or gravitational potential difference. In special
relativity, a moving clock runs slower than a stationary clock by factor
γ = 1/√(1 - v²/c²).

Sources:
- Time dilation (definition)
- Special relativity (theory)
- Lorentz transformation (mathematics)
```

## Performance

### Evaluation Results

Tested on 75 physics questions across 4 domains:

| Metric       | Physics Pack | Web Search | Training Data |
|--------------|--------------|------------|---------------|
| Accuracy     | **84.7%**    | 71.5%      | 62.3%         |
| F1 Score     | **0.81**     | 0.67       | 0.58          |
| Avg Latency  | **0.9s**     | 3.8s       | 1.2s          |

**Key insights:**
- 22% more accurate than training data baseline
- 13% more accurate than web search
- 4.2x faster than web search

### Query Performance

Typical query latencies:

- Easy questions (definitions): 0.7s
- Medium questions (multi-hop): 0.9s
- Hard questions (complex reasoning): 1.0s

Cache hit rate: ~65% for repeated queries

## Pack Structure

```
physics-expert/
├── manifest.json           # Pack metadata
├── database.db            # Kuzu knowledge graph
├── embeddings/            # Vector embeddings for entities
│   └── entity_embeddings.npy
├── articles/              # Source article text
│   ├── article_00000.json
│   ├── article_00001.json
│   └── ...
└── metadata/
    ├── seed_topics.txt    # Original 500 seed topics
    └── build_config.json  # Build configuration
```

## Build Configuration

This pack was built with:

```json
{
    "seeds": "seeds/physics-500.txt",
    "max_depth": 3,
    "max_articles": 6000,
    "language": "en",
    "exclude_categories": [
        "Category:Science fiction",
        "Category:Pseudoscience"
    ],
    "min_links": 5,
    "llm_model": "claude-3-5-sonnet-20241022",
    "relationship_types": [
        "relatedTo",
        "derivedFrom",
        "measuredBy",
        "discoveredBy",
        "appliesTo"
    ]
}
```

## Troubleshooting

### Installation fails

```bash
# Check WikiGR version
wikigr --version
# Requires: 1.0.0+

# Check disk space
df -h ~/.wikigr/packs/
# Requires: 1.2 GB
```

### Queries return empty results

```bash
# Verify pack integrity
wikigr pack validate physics-expert

# Rebuild index if needed
wikigr pack reindex physics-expert
```

### Slow queries

```python
# Enable caching
agent = KGAgent(pack.graph, enable_cache=True)

# Reduce entity limit
result = agent.answer(question, max_entities=5)

# Warm up cache with common queries
agent.warmup_cache(common_questions)
```

## Updates and Versioning

### Version History

- **v1.0.0** (2026-02-24): Initial release
  - 5,247 articles across 4 domains
  - 14,382 entities, 23,198 relationships
  - Evaluated on 75 questions (84.7% accuracy)

### Update Policy

Packs are updated when:
- New physics discoveries require coverage
- Wikipedia articles have significant updates
- Evaluation identifies coverage gaps
- Community requests specific topics

Check for updates:

```bash
wikigr pack check-updates physics-expert
```

## License and Attribution

### Content License

All article content is sourced from Wikipedia and licensed under **CC BY-SA 3.0**.

Full article attributions: See `ATTRIBUTIONS.txt` in pack distribution.

### Usage Requirements

When using this pack:
1. Attribute Wikipedia as the source
2. Share adaptations under same license (CC BY-SA 3.0)
3. Include link to original Wikipedia articles
4. Indicate if changes were made

### Citation

If citing this pack in research:

```bibtex
@misc{physicsexpert2026,
  title={Physics-Expert Knowledge Pack for WikiGR},
  author={WikiGR Contributors},
  year={2026},
  publisher={GitHub},
  url={https://github.com/yourorg/wikigr-packs}
}
```

## Support

- **Documentation:** [Full docs](../../docs/packs/physics-expert/README.md)
- **Evaluation details:** [EVALUATION.md](../../docs/packs/physics-expert/EVALUATION.md)
- **Create your own:** [HOW_TO_CREATE_YOUR_OWN.md](../../docs/packs/HOW_TO_CREATE_YOUR_OWN.md)
- **Issues:** https://github.com/yourorg/wikigr/issues
- **Discussions:** https://github.com/yourorg/wikigr/discussions

## Contributing

Help improve this pack:

1. **Report gaps:** Open issue with missing topics
2. **Suggest seeds:** Submit PR with additional seed topics
3. **Improve evaluation:** Add test questions
4. **Share feedback:** Comment on usage experience

## Acknowledgments

- Wikipedia contributors (5,247 articles)
- Domain experts (seed topic curation)
- Anthropic Claude (entity extraction)
- WikiGR community (testing and feedback)

---

**Created with WikiGR 1.0.0** | [Create your own pack](../../docs/packs/HOW_TO_CREATE_YOUR_OWN.md)
