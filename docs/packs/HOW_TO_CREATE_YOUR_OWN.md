# How to Create Your Own Knowledge Pack

A step-by-step guide to building domain-specific knowledge packs using WikiGR. Learn from the physics-expert pack creation process.

## Overview

Creating a knowledge pack involves five stages:

1. **Curate Topics** - Select seed articles for your domain
2. **Build the Graph** - Expand seeds into a full knowledge graph
3. **Create Evaluation** - Design questions to measure quality
4. **Run Evaluation** - Compare pack against baselines
5. **Package and Distribute** - Create shareable pack file

**Time estimate:** 2-4 hours for a 5,000-article pack

**Prerequisites:**
- WikiGR 1.0.0 or later
- Python 3.10+
- Anthropic API key (for evaluation)

## Step 1: Curate Topics

### Choose Your Domain

Select a focused domain with clear boundaries:

**Good domains:**
- Physics (classical, quantum, thermo, relativity)
- Medieval history (800-1500 CE)
- Machine learning (algorithms, architectures)
- Organic chemistry (molecules, reactions)

**Avoid:**
- Too broad: "Science" (millions of articles)
- Too narrow: "Schrödinger's cat" (dozens of articles)
- Ambiguous: "Technology" (no clear boundaries)

**Target size:** 4,000-6,000 articles (from 400-600 seed topics)

### Seed Selection Strategies

#### Strategy 1: Expert Curation (Recommended)

Domain experts manually select foundational topics:

```bash
# Create seed file
cat > seeds/my-domain-seeds.txt <<EOF
# Foundational concepts
Topic Name 1
Topic Name 2

# Key subtopics
Subtopic A
Subtopic B

# Important methods/tools
Method X
Method Y
EOF
```

**Physics-expert example:**

```
# Classical Mechanics (125 topics)
Newton's laws of motion
Conservation of energy
Angular momentum
Kepler's laws of planetary motion

# Quantum Mechanics (150 topics)
Wave-particle duality
Heisenberg uncertainty principle
Schrödinger equation
Quantum entanglement

# Thermodynamics (100 topics)
Laws of thermodynamics
Entropy
Carnot cycle
Maxwell-Boltzmann distribution

# Relativity (125 topics)
Special relativity
General relativity
Time dilation
Gravitational waves
```

**Best practices:**

- **Aim for 400-600 seeds** (typical expansion: 8-12x)
- **Cover all subdomains** evenly (physics: 4 domains × 125 topics)
- **Include foundational topics** (laws, principles, key figures)
- **Add bridging topics** (connecting subdomains)
- **Validate with experts** (subject matter review)

#### Strategy 2: Wikipedia Category Mining

Extract topics from Wikipedia categories:

```python
from wikigr.pack_builder import CategoryMiner

miner = CategoryMiner()
seeds = miner.extract_from_categories(
    categories=[
        "Category:Physics",
        "Category:Quantum mechanics",
        "Category:Classical mechanics"
    ],
    max_depth=2,  # Subcategory depth
    max_articles=500
)

# Save to file
with open("seeds/auto-seeds.txt", "w") as f:
    f.write("\n".join(seeds))
```

**Pros:** Fast, comprehensive coverage

**Cons:** May include tangential articles, requires manual filtering

#### Strategy 3: Citation Network Sampling

Find highly-cited articles in domain:

```python
from wikigr.pack_builder import CitationSampler

sampler = CitationSampler()
seeds = sampler.find_top_cited(
    root_articles=["Physics", "Quantum mechanics"],
    min_citations=100,
    max_articles=500
)
```

**Pros:** High-quality, frequently referenced articles

**Cons:** May miss niche but important topics

### Validate Your Seeds

Check seed coverage before expansion:

```bash
# Validate seeds exist on Wikipedia
wikigr pack validate-seeds seeds/my-domain-seeds.txt

# Output:
# ✓ 485/500 seeds found on Wikipedia
# ✗ 15 seeds not found (see seeds/errors.txt)
# Estimated expansion: 4,850 articles (10x)
```

## Step 2: Build the Graph

### Basic Pack Build

Create a knowledge pack from seeds:

```bash
wikigr pack build my-domain-pack \
    --seeds seeds/my-domain-seeds.txt \
    --max-depth 3 \
    --max-articles 6000 \
    --output packs/
```

**Parameters:**

- `--max-depth`: Graph traversal depth (2-4 typical)
  - Depth 2: Conservative, ~5x expansion
  - Depth 3: Balanced, ~10x expansion (recommended)
  - Depth 4: Aggressive, ~15x expansion (may include noise)

- `--max-articles`: Stop after N articles
  - 4,000-6,000 recommended for focused domains
  - More articles ≠ better quality (diminishing returns)

- `--output`: Directory for pack files

### Advanced Configuration

Fine-tune expansion with filters:

```bash
wikigr pack build physics-expert \
    --seeds seeds/physics-500.txt \
    --max-depth 3 \
    --max-articles 6000 \
    --exclude-categories "Category:Science fiction" \
    --min-links 5 \
    --language en \
    --output packs/
```

**Advanced parameters:**

- `--exclude-categories`: Block unwanted topics
- `--min-links`: Minimum inbound links (filters stub articles)
- `--language`: Wikipedia language edition (default: en)
- `--date-range`: Filter articles by creation date

### Monitor Progress

Track build progress in real-time:

```bash
# Build with verbose logging
wikigr pack build my-pack --seeds seeds.txt --verbose

# Output:
# [1/5] Loading seed articles... 500 seeds loaded
# [2/5] Expanding graph (depth=1)... 2,143 articles
# [3/5] Expanding graph (depth=2)... 4,782 articles
# [4/5] Extracting entities with LLM... 3,421/4,782 (71%)
# [5/5] Building knowledge graph... Done!
#
# Pack created: my-pack.tar.gz (1.1 GB)
# - Articles: 4,782
# - Entities: 12,456
# - Relationships: 19,834
```

### Entity Extraction

The build process extracts structured knowledge using Claude:

```python
# For each article, Claude extracts:
{
    "article_title": "Quantum entanglement",
    "entities": [
        {
            "name": "Quantum entanglement",
            "type": "Phenomenon",
            "description": "Physical phenomenon in quantum mechanics"
        },
        {
            "name": "Albert Einstein",
            "type": "Scientist",
            "description": "Physicist who questioned entanglement"
        }
    ],
    "relationships": [
        {
            "from": "Quantum entanglement",
            "to": "EPR paradox",
            "type": "relatedTo"
        },
        {
            "from": "Albert Einstein",
            "to": "EPR paradox",
            "type": "discoveredBy"
        }
    ]
}
```

**Relationship types:**

- `relatedTo`: General conceptual connection
- `derivedFrom`: Theoretical foundation
- `measuredBy`: Experimental method
- `discoveredBy`: Historical attribution
- `appliesTo`: Practical application

**Cost estimate:** ~$5-10 for 5,000 articles (using Claude 3.5 Sonnet)

## Step 3: Create Evaluation Questions

### Question Design

Create 50-100 questions across your domain:

```json
{
    "questions": [
        {
            "id": 1,
            "question": "What is quantum entanglement?",
            "domain": "quantum_mechanics",
            "difficulty": "easy",
            "expected_entities": [
                "Quantum_entanglement",
                "EPR_paradox",
                "Bell_test"
            ],
            "gold_answer": "Quantum entanglement is a phenomenon where particles become correlated such that the state of one particle instantaneously affects the state of another, regardless of distance."
        }
    ]
}
```

**Question distribution:**

| Category   | Count | Purpose                          |
|------------|-------|----------------------------------|
| Easy       | 30%   | Basic definitions, single-hop    |
| Medium     | 40%   | Multi-hop reasoning, connections |
| Hard       | 30%   | Complex derivations, edge cases  |

### Question Types

**1. Definitional (Easy)**

```json
{
    "question": "What is the second law of thermodynamics?",
    "difficulty": "easy",
    "expected_answer_type": "definition"
}
```

**2. Relational (Medium)**

```json
{
    "question": "How does the uncertainty principle relate to wave-particle duality?",
    "difficulty": "medium",
    "expected_answer_type": "explanation"
}
```

**3. Analytical (Hard)**

```json
{
    "question": "Why does time dilation in special relativity not violate causality?",
    "difficulty": "hard",
    "expected_answer_type": "reasoning"
}
```

### Quality Criteria

Every question must be:

- **Answerable**: From pack content (not external knowledge)
- **Unambiguous**: Single clear interpretation
- **Verifiable**: Gold answer from authoritative source
- **Representative**: Covers important domain concepts
- **Diverse**: Multiple question types and difficulties

### Generate Questions (Semi-Automated)

Use Claude to draft questions from pack content:

```python
from wikigr.evaluation import QuestionGenerator

generator = QuestionGenerator(pack_path="packs/my-pack.tar.gz")

# Generate draft questions
questions = generator.generate(
    num_questions=75,
    difficulty_distribution={"easy": 0.3, "medium": 0.4, "hard": 0.3},
    domains=["domain1", "domain2", "domain3"]
)

# Save for manual review
generator.save(questions, "eval/draft-questions.json")
```

**IMPORTANT:** Always manually review and validate generated questions.

## Step 4: Run Evaluation

### Configure Baselines

Compare your pack against three baselines:

**1. Training Data (Claude only)**

```python
from wikigr.evaluation import TrainingDataBaseline

baseline = TrainingDataBaseline(
    model="claude-3-5-sonnet-20241022",
    api_key=os.environ["ANTHROPIC_API_KEY"]
)
```

**2. Web Search (Claude + Brave)**

```python
from wikigr.evaluation import WebSearchBaseline

baseline = WebSearchBaseline(
    model="claude-3-5-sonnet-20241022",
    search_api="brave",
    api_key=os.environ["ANTHROPIC_API_KEY"],
    brave_api_key=os.environ["BRAVE_API_KEY"]
)
```

**3. Knowledge Pack (Claude + Your Pack)**

```python
from wikigr.evaluation import PackBaseline
from wikigr.packs import PackManager

manager = PackManager()
pack = manager.load("my-pack")

baseline = PackBaseline(
    model="claude-3-5-sonnet-20241022",
    pack=pack,
    api_key=os.environ["ANTHROPIC_API_KEY"]
)
```

### Run Evaluation

Execute full evaluation:

```bash
# Set API keys
export ANTHROPIC_API_KEY="sk-ant-..."
export BRAVE_API_KEY="BSA..."

# Run evaluation
wikigr evaluate \
    --pack my-pack \
    --questions eval/questions.json \
    --baselines training_data,web_search,pack \
    --output results/ \
    --verbose
```

### Interpret Results

Look for:

**1. Pack Outperforms Baselines**

```
Target: Pack accuracy > Web search accuracy + 10%
Example: Pack 84.7% vs Web 71.5% ✓
```

**2. Consistent Domain Coverage**

```
No domain should lag more than 15% below average
Example: All domains 81-88% ✓
```

**3. Difficulty Gradient**

```
Easy > Medium > Hard (with reasonable gaps)
Example: 93% → 85% → 76% ✓
```

**4. Fast Response Times**

```
Pack latency < Web search latency
Example: 0.9s vs 3.8s ✓
```

### Iterate if Needed

If results are poor:

**Low accuracy (< 70%):**
- Add more seed topics (expand coverage)
- Increase max-depth (capture more connections)
- Review question quality (too hard?)

**High latency (> 2s):**
- Enable caching (`enable_cache=True`)
- Reduce `max_entities` in KG Agent
- Optimize graph indices

**Domain imbalance:**
- Rebalance seed topics across domains
- Add bridging articles between weak domains

## Step 5: Package and Distribute

### Validate Pack

Check pack integrity before distribution:

```bash
wikigr pack validate my-pack.tar.gz

# Output:
# ✓ Pack structure valid
# ✓ Manifest complete (version, metadata)
# ✓ Database integrity verified (4,782 articles)
# ✓ Embeddings valid (12,456 entities)
# ✓ Graph traversable (19,834 relationships)
# ✓ No orphan entities
```

### Create Distribution Package

Add documentation and metadata:

```bash
# Create pack directory
mkdir -p my-pack-dist

# Copy pack file
cp packs/my-pack.tar.gz my-pack-dist/

# Add documentation
cat > my-pack-dist/README.md <<EOF
# My Domain Knowledge Pack

A specialized knowledge graph for [domain description].

## Installation

\`\`\`bash
wikigr pack install my-pack.tar.gz
\`\`\`

## Usage

\`\`\`bash
wikigr kg-query "Your question" --pack my-pack
\`\`\`

## Contents

- Articles: 4,782
- Entities: 12,456
- Relationships: 19,834
- Domains: Domain1, Domain2, Domain3

## License

CC BY-SA 3.0 (Wikipedia content)
EOF

# Add attributions
wikigr pack attributions my-pack.tar.gz > my-pack-dist/ATTRIBUTIONS.txt

# Create release archive
tar -czf my-pack-v1.0.0.tar.gz my-pack-dist/
```

### Share the Pack

**Option 1: GitHub Release**

```bash
gh release create v1.0.0 \
    my-pack-v1.0.0.tar.gz \
    --title "My Pack v1.0.0" \
    --notes "Initial release"
```

**Option 2: Pack Registry (Future)**

```bash
wikigr pack publish my-pack-v1.0.0.tar.gz \
    --registry https://packs.wikigr.org \
    --category science
```

**Option 3: Direct Distribution**

Host the `.tar.gz` file on your infrastructure:

```bash
# Users install with:
wikigr pack install https://yoursite.com/packs/my-pack-v1.0.0.tar.gz
```

## Tips and Best Practices

### Seed Curation

✅ **Do:**
- Consult domain experts for seed selection
- Balance coverage across subdomains
- Include foundational topics and bridging concepts
- Validate seeds exist on Wikipedia before expansion

❌ **Don't:**
- Rely solely on automated category mining
- Over-represent niche subtopics
- Include stub articles or disambiguation pages
- Expand beyond domain boundaries

### Graph Expansion

✅ **Do:**
- Start with depth=3 (balanced expansion)
- Set reasonable article limits (4K-6K)
- Monitor expansion progress
- Use category filters to block noise

❌ **Don't:**
- Use depth > 4 (diminishing returns)
- Build packs > 10K articles (slow, unfocused)
- Skip entity extraction (breaks graph traversal)
- Ignore orphan articles in validation

### Evaluation Design

✅ **Do:**
- Write 50-100 diverse questions
- Include all difficulty levels
- Compare multiple baselines
- Manually review gold answers

❌ **Don't:**
- Rely on auto-generated questions only
- Test only easy questions
- Compare against single baseline
- Skip reproducibility testing

### Distribution

✅ **Do:**
- Validate pack before distribution
- Include clear installation instructions
- Provide usage examples
- Credit Wikipedia (CC BY-SA 3.0)

❌ **Don't:**
- Distribute invalid packs
- Omit documentation
- Forget attribution requirements
- Version packs inconsistently

## Common Pitfalls

### Pitfall 1: Domain Too Broad

**Problem:** "Science pack" with 50K articles performs worse than focused packs

**Solution:** Narrow scope to specific subdomain (physics, chemistry, biology separately)

### Pitfall 2: Insufficient Evaluation

**Problem:** Pack seems good but fails on real usage

**Solution:** Create rigorous evaluation with 75+ questions across difficulties

### Pitfall 3: Over-Expansion

**Problem:** Depth=5 expansion includes tangential articles (physics → history of science → biographies)

**Solution:** Use depth=3 with category filters

### Pitfall 4: No Bridging Topics

**Problem:** Subdomains disconnected, multi-hop queries fail

**Solution:** Include topics connecting subdomains (e.g., "Quantum thermodynamics" bridges quantum + thermo)

### Pitfall 5: Ignoring Latency

**Problem:** Pack queries slow despite local graph

**Solution:** Enable caching, optimize max_entities, check graph indices

## Example Pack Specifications

### Physics-Expert

- **Seeds:** 500 expert-curated topics
- **Expansion:** Depth=3, max=6,000
- **Result:** 5,247 articles, 14,382 entities
- **Evaluation:** 75 questions, 84.7% accuracy
- **Time:** 3 hours (2h build, 1h evaluation)

### Medieval-History

- **Seeds:** 400 topics (800-1500 CE)
- **Expansion:** Depth=3, max=5,000
- **Result:** 4,891 articles, 11,234 entities
- **Evaluation:** 60 questions, 79.3% accuracy
- **Time:** 2.5 hours

### Machine-Learning

- **Seeds:** 600 topics (algorithms, architectures)
- **Expansion:** Depth=2, max=4,000
- **Result:** 3,782 articles, 9,876 entities
- **Evaluation:** 80 questions, 81.2% accuracy
- **Time:** 2 hours

## Next Steps

- **Use the physics-expert pack**: See [docs/packs/physics-expert/README.md](./physics-expert/README.md)
- **Understand evaluation**: See [docs/packs/physics-expert/EVALUATION.md](./physics-expert/EVALUATION.md)
- **API reference**: See [docs/reference/kg-agent-api.md](../reference/kg-agent-api.md)
- **CLI commands**: See [docs/CLI_PACK_COMMANDS.md](../CLI_PACK_COMMANDS.md)
- **Share your pack**: Open PR to add to pack registry

## Community Packs

Contribute your pack to the community:

1. Create pack following this guide
2. Run evaluation and document results
3. Open PR to `wikigr-packs` repository
4. Community review and approval
5. Listed in official pack registry

**Current community packs:**
- physics-expert (5,247 articles) - Classical, quantum, thermo, relativity
- medieval-history (4,891 articles) - 800-1500 CE European history
- machine-learning (3,782 articles) - ML algorithms and architectures

## Support

- **Documentation:** https://docs.wikigr.org
- **Issues:** https://github.com/yourorg/wikigr/issues
- **Discussions:** https://github.com/yourorg/wikigr/discussions
- **Pack Registry:** https://packs.wikigr.org
