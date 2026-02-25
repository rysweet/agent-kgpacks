# Knowledge Packs Implementation Guide

This guide shows which files to modify when implementing the Knowledge Packs feature. It maps design phases to specific code modules and provides implementation order.

## Quick Reference

| Phase | Component | Files to Modify | Priority |
|-------|-----------|----------------|----------|
| 0 | Evaluation Framework | `backend/evaluation/`, `cli/eval.py` | **FIRST** |
| 1 | Pack Format | `backend/packs/manifest.py`, `backend/packs/validator.py` | High |
| 2 | Skill Integration | `backend/packs/skill_generator.py`, `data/packs/*/skill.md` | High |
| 3 | Pack Builder CLI | `cli/pack_build.py`, `backend/packs/builder.py` | Medium |
| 4 | Distribution System | `cli/pack_install.py`, `backend/packs/installer.py` | Medium |
| 5 | Quality Assurance | `tests/packs/`, CI workflows | High |

## Phase 0: Evaluation Framework (IMPLEMENT FIRST)

**Why first?** The entire value proposition hinges on "packs beat baselines by X%". Must validate this claim before investing in infrastructure.

### Files to Create

```
backend/evaluation/
├── __init__.py
├── baselines.py           # TrainingDataBaseline, WebSearchBaseline, PackBaseline
├── metrics.py             # Accuracy, F1, Latency scoring
├── runner.py              # EvaluationRunner orchestration
└── question_loader.py     # Load questions from JSONL

cli/
└── eval.py                # CLI command: wikigr pack eval <pack-name>

tests/evaluation/
├── test_baselines.py      # Unit tests for each baseline
├── test_metrics.py        # Test scoring functions
└── fixtures/
    └── sample_questions.jsonl  # Test question set
```

### Implementation Order

1. **Create metrics.py** - Scoring functions (accuracy, F1, latency)
2. **Create baselines.py** - Three baseline classes
3. **Create question_loader.py** - JSONL parsing and validation
4. **Create runner.py** - Orchestrate evaluation across baselines
5. **Create cli/eval.py** - CLI wrapper for runner
6. **Write tests** - Verify metrics and baselines work correctly

### Key Interfaces

```python
# backend/evaluation/baselines.py
class Baseline(ABC):
    @abstractmethod
    def query(self, question: str) -> BaselineResult:
        """Query the baseline with a question."""
        pass

class TrainingDataBaseline(Baseline):
    def __init__(self, model: str, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def query(self, question: str) -> BaselineResult:
        # Direct Claude query, no retrieval
        pass

class WebSearchBaseline(Baseline):
    def __init__(self, model: str, api_key: str, search_api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.search_client = BraveSearch(api_key=search_api_key)
        self.model = model

    def query(self, question: str) -> BaselineResult:
        # Claude + Brave Search
        pass

class PackBaseline(Baseline):
    def __init__(self, model: str, api_key: str, pack: KnowledgePack):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.agent = KGAgent(pack.graph, config_path=pack.kg_config_path)
        self.model = model

    def query(self, question: str) -> BaselineResult:
        # Claude + Pack retrieval
        pass
```

```python
# backend/evaluation/metrics.py
def score_accuracy(answer: str, gold_answer: str) -> float:
    """Score factual accuracy using semantic similarity + fact overlap."""
    embedding_sim = cosine_similarity(embed(answer), embed(gold_answer))
    fact_overlap = jaccard_similarity(extract_facts(answer), extract_facts(gold_answer))
    return 0.6 * embedding_sim + 0.4 * fact_overlap

def score_f1(cited_entities: list[str], expected_entities: list[str]) -> float:
    """F1 score for source relevance."""
    precision = len(set(cited_entities) & set(expected_entities)) / len(cited_entities)
    recall = len(set(cited_entities) & set(expected_entities)) / len(expected_entities)
    return 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

def measure_latency(func: Callable) -> tuple[Any, float]:
    """Measure execution time of a function."""
    start = time.time()
    result = func()
    latency = time.time() - start
    return result, latency
```

### CLI Integration

```python
# cli/eval.py
import click
from backend.evaluation import EvaluationRunner

@click.command()
@click.argument('pack_name')
@click.option('--questions', required=True, help='Path to questions JSONL file')
@click.option('--baselines', default='all', help='Comma-separated: training_data,web_search,pack')
@click.option('--output', default='results/', help='Output directory for results')
@click.option('--verbose', is_flag=True, help='Show detailed progress')
def eval_pack(pack_name: str, questions: str, baselines: str, output: str, verbose: bool):
    """Evaluate a knowledge pack against baselines."""
    runner = EvaluationRunner(
        pack_name=pack_name,
        questions_path=questions,
        baselines=baselines.split(','),
        output_dir=output,
        verbose=verbose
    )
    results = runner.run()
    click.echo(f"Evaluation complete. Results saved to {output}")
```

### Testing Strategy

```python
# tests/evaluation/test_baselines.py
def test_training_data_baseline():
    baseline = TrainingDataBaseline(model="claude-3-5-sonnet-20241022", api_key="test")
    result = baseline.query("What is quantum entanglement?")

    assert result.answer is not None
    assert isinstance(result.latency, float)
    assert result.latency > 0

def test_pack_baseline_with_mock_pack():
    mock_pack = create_mock_pack()
    baseline = PackBaseline(model="claude-3-5-sonnet-20241022", api_key="test", pack=mock_pack)

    result = baseline.query("What is Newton's first law?")

    assert result.answer is not None
    assert len(result.sources) > 0
    assert result.latency < 5.0  # Should be fast with local retrieval
```

## Phase 1: Pack Format & Manifest

### Files to Create

```
backend/packs/
├── __init__.py
├── manifest.py            # PackManifest dataclass, validation
├── validator.py           # Validate pack structure and integrity
└── schema.py              # JSON schemas for manifest.json, kg_config.json

data/packs/
└── [pack-name]/
    ├── manifest.json      # Pack metadata
    ├── kg_config.json     # KG Agent configuration
    ├── pack.db            # Kuzu database
    ├── skill.md           # Claude Code skill
    ├── eval/
    │   ├── questions.jsonl
    │   └── README.md
    └── README.md
```

### Implementation Order

1. **Create manifest.py** - Define `PackManifest` dataclass
2. **Create schema.py** - JSON schemas for validation
3. **Create validator.py** - Validate pack structure, manifest, database
4. **Write tests** - Test manifest parsing and validation

### Key Interfaces

```python
# backend/packs/manifest.py
from dataclasses import dataclass
from pathlib import Path

@dataclass
class PackManifest:
    name: str
    version: str
    description: str
    author: str
    license: str
    homepage: str

    knowledge_base: dict  # stats, sources, domains
    skill: dict           # interface, activation_keywords, kg_config
    evaluation: dict      # benchmark_dir, baseline_scores
    requirements: dict    # versions, disk_space
    metadata: dict        # created, updated, tags

    @classmethod
    def from_file(cls, path: Path) -> "PackManifest":
        """Load manifest from JSON file."""
        with open(path) as f:
            data = json.load(f)
        return cls(**data)

    def validate(self) -> list[str]:
        """Validate manifest fields. Returns list of errors."""
        errors = []
        if not self.name or not self.name.isidentifier():
            errors.append(f"Invalid pack name: {self.name}")
        if not self.version or not re.match(r'^\d+\.\d+\.\d+$', self.version):
            errors.append(f"Invalid version: {self.version}")
        # ... more validation
        return errors
```

```python
# backend/packs/validator.py
class PackValidator:
    def __init__(self, pack_dir: Path):
        self.pack_dir = pack_dir

    def validate_structure(self) -> list[str]:
        """Validate pack directory structure."""
        errors = []
        required_files = ["manifest.json", "kg_config.json", "pack.db", "skill.md"]

        for file in required_files:
            if not (self.pack_dir / file).exists():
                errors.append(f"Missing required file: {file}")

        return errors

    def validate_database(self) -> list[str]:
        """Validate Kuzu database integrity."""
        errors = []
        db_path = self.pack_dir / "pack.db"

        try:
            conn = kuzu.Connection(str(db_path))
            # Check tables exist
            tables = conn.execute("MATCH (n) RETURN labels(n) LIMIT 1").get_as_df()
            if tables.empty:
                errors.append("Database is empty")
        except Exception as e:
            errors.append(f"Database error: {e}")

        return errors

    def validate_manifest(self) -> list[str]:
        """Validate manifest.json."""
        manifest_path = self.pack_dir / "manifest.json"
        manifest = PackManifest.from_file(manifest_path)
        return manifest.validate()

    def validate_all(self) -> dict[str, list[str]]:
        """Run all validations."""
        return {
            "structure": self.validate_structure(),
            "database": self.validate_database(),
            "manifest": self.validate_manifest()
        }
```

## Phase 2: Skill Integration

### Files to Create

```
backend/packs/
└── skill_generator.py     # Generate skill.md from pack metadata

cli/
└── pack_skill.py          # CLI: wikigr pack generate-skill <pack-name>
```

### Implementation Order

1. **Create skill_generator.py** - Template-based skill.md generation
2. **Create skill template** - Jinja2 template for skill.md
3. **Integrate with pack builder** - Auto-generate skill on pack creation
4. **Write tests** - Verify generated skills are valid

### Key Interfaces

```python
# backend/packs/skill_generator.py
from jinja2 import Template

class SkillGenerator:
    def __init__(self, manifest: PackManifest):
        self.manifest = manifest

    def generate(self, output_path: Path):
        """Generate skill.md from manifest."""
        template = self._load_template()

        skill_content = template.render(
            name=self.manifest.name,
            version=self.manifest.version,
            description=self.manifest.description,
            domains=self.manifest.knowledge_base.get("domains", []),
            activation_keywords=self.manifest.skill.get("activation_keywords", []),
            kg_config_path=f"~/.wikigr/packs/{self.manifest.name}/kg_config.json"
        )

        output_path.write_text(skill_content)

    def _load_template(self) -> Template:
        """Load Jinja2 template for skill.md."""
        template_path = Path(__file__).parent / "templates" / "skill.md.j2"
        return Template(template_path.read_text())
```

## Phase 3: Pack Builder CLI

### Files to Create

```
cli/
├── pack_build.py          # CLI: wikigr pack build
└── pack_validate.py       # CLI: wikigr pack validate

backend/packs/
├── builder.py             # PackBuilder class
├── graph_expander.py      # Wikipedia graph traversal
└── entity_extractor.py    # LLM-based entity extraction
```

### Implementation Order

1. **Create graph_expander.py** - BFS traversal from seed articles
2. **Create entity_extractor.py** - Claude-based entity/relationship extraction
3. **Create builder.py** - Orchestrate pack building process
4. **Create pack_build.py CLI** - User-facing command
5. **Write tests** - Test with small seed sets

### Key Interfaces

```python
# backend/packs/builder.py
class PackBuilder:
    def __init__(self, name: str, seeds: list[str], max_depth: int, max_articles: int):
        self.name = name
        self.seeds = seeds
        self.max_depth = max_depth
        self.max_articles = max_articles

    def build(self, output_dir: Path) -> Path:
        """Build a knowledge pack."""
        # 1. Expand graph from seeds
        articles = self._expand_graph()

        # 2. Extract entities with LLM
        entities, relationships = self._extract_knowledge(articles)

        # 3. Create Kuzu database
        db_path = self._create_database(articles, entities, relationships)

        # 4. Generate embeddings
        self._generate_embeddings(db_path)

        # 5. Create manifest
        manifest = self._create_manifest(articles, entities, relationships)

        # 6. Generate skill
        self._generate_skill(manifest)

        # 7. Package as tar.gz
        return self._package(output_dir)

    def _expand_graph(self) -> list[Article]:
        """BFS traversal from seed articles."""
        expander = GraphExpander(self.seeds, self.max_depth, self.max_articles)
        return expander.expand()

    def _extract_knowledge(self, articles: list[Article]) -> tuple[list[Entity], list[Relationship]]:
        """Extract entities and relationships using Claude."""
        extractor = EntityExtractor(model="claude-3-5-sonnet-20241022")
        return extractor.extract_batch(articles)
```

## Phase 4: Distribution & Installation

### Files to Create

```
cli/
├── pack_install.py        # CLI: wikigr pack install
├── pack_list.py           # CLI: wikigr pack list
└── pack_uninstall.py      # CLI: wikigr pack uninstall

backend/packs/
├── installer.py           # PackInstaller class
├── registry.py            # (Future) Pack registry client
└── manager.py             # PackManager - load/unload packs
```

### Implementation Order

1. **Create installer.py** - Extract and install pack tarballs
2. **Create manager.py** - Load/unload packs at runtime
3. **Create CLI commands** - install, list, uninstall
4. **Write tests** - Test install/uninstall with mock packs

### Key Interfaces

```python
# backend/packs/installer.py
class PackInstaller:
    def __init__(self, install_dir: Path = None):
        self.install_dir = install_dir or Path.home() / ".wikigr" / "packs"

    def install(self, source: str) -> Path:
        """
        Install a pack from:
        - Local file: physics-expert.tar.gz
        - URL: https://example.com/packs/physics-expert.tar.gz
        - Name (registry): physics-expert
        """
        if source.endswith(".tar.gz"):
            return self._install_from_file(Path(source))
        elif source.startswith("http"):
            return self._install_from_url(source)
        else:
            return self._install_from_registry(source)

    def _install_from_file(self, tarball: Path) -> Path:
        """Extract tarball to ~/.wikigr/packs/"""
        with tarfile.open(tarball, "r:gz") as tar:
            tar.extractall(self.install_dir)

        # Validate installation
        pack_name = tarball.stem.replace(".tar", "")
        pack_dir = self.install_dir / pack_name
        validator = PackValidator(pack_dir)
        errors = validator.validate_all()

        if any(errors.values()):
            raise ValueError(f"Invalid pack: {errors}")

        return pack_dir
```

```python
# backend/packs/manager.py
class PackManager:
    def __init__(self, packs_dir: Path = None):
        self.packs_dir = packs_dir or Path.home() / ".wikigr" / "packs"

    def list_installed(self) -> list[PackManifest]:
        """List all installed packs."""
        packs = []
        for pack_dir in self.packs_dir.iterdir():
            if pack_dir.is_dir() and (pack_dir / "manifest.json").exists():
                manifest = PackManifest.from_file(pack_dir / "manifest.json")
                packs.append(manifest)
        return packs

    def load(self, name: str) -> KnowledgePack:
        """Load a pack for use."""
        pack_dir = self.packs_dir / name
        if not pack_dir.exists():
            raise ValueError(f"Pack not found: {name}")

        manifest = PackManifest.from_file(pack_dir / "manifest.json")
        db_path = pack_dir / "pack.db"
        kg_config_path = pack_dir / "kg_config.json"

        return KnowledgePack(
            name=name,
            manifest=manifest,
            graph=kuzu.Connection(str(db_path)),
            kg_config_path=kg_config_path
        )
```

## Phase 5: Quality Assurance

### Files to Create

```
tests/packs/
├── test_manifest.py
├── test_validator.py
├── test_builder.py
├── test_installer.py
├── test_skill_generator.py
└── fixtures/
    └── test_pack/
        ├── manifest.json
        ├── kg_config.json
        └── pack.db

.github/workflows/
└── test-packs.yml         # CI workflow for pack testing
```

### Testing Strategy

1. **Unit tests** - Test each module in isolation
2. **Integration tests** - Test pack build, install, query workflow
3. **Evaluation tests** - Verify baseline comparison works
4. **Performance tests** - Ensure latency targets met

## Module Organization

```
backend/
├── packs/
│   ├── __init__.py
│   ├── manifest.py        # PackManifest dataclass
│   ├── validator.py       # PackValidator
│   ├── builder.py         # PackBuilder
│   ├── installer.py       # PackInstaller
│   ├── manager.py         # PackManager
│   ├── skill_generator.py # SkillGenerator
│   ├── graph_expander.py  # GraphExpander (Wikipedia BFS)
│   └── entity_extractor.py # EntityExtractor (LLM-based)
│
├── evaluation/
│   ├── __init__.py
│   ├── baselines.py       # Baseline classes
│   ├── metrics.py         # Scoring functions
│   ├── runner.py          # EvaluationRunner
│   └── question_loader.py # JSONL parsing
│
└── kg_agent.py            # Existing KGAgent (enhanced with pack support)

cli/
├── pack_build.py          # wikigr pack build
├── pack_install.py        # wikigr pack install
├── pack_list.py           # wikigr pack list
├── pack_validate.py       # wikigr pack validate
└── eval.py                # wikigr pack eval

data/packs/
└── [pack-name]/           # Installed packs
    ├── manifest.json
    ├── kg_config.json
    ├── pack.db
    ├── skill.md
    ├── eval/
    └── README.md
```

## Development Workflow

### Step 1: Implement Evaluation First

```bash
# Create evaluation framework
touch backend/evaluation/{__init__.py,baselines.py,metrics.py,runner.py}

# Write tests
touch tests/evaluation/test_baselines.py

# Verify evaluation works BEFORE building packs
pytest tests/evaluation/
```

### Step 2: Implement Pack Format

```bash
# Create pack modules
touch backend/packs/{__init__.py,manifest.py,validator.py}

# Create test fixtures
mkdir -p tests/packs/fixtures/test_pack

# Test manifest parsing
pytest tests/packs/test_manifest.py
```

### Step 3: Build Small Prototype Pack

```bash
# Manually create a 10-article test pack
# Validate format works

wikigr pack validate tests/packs/fixtures/test_pack
```

### Step 4: Implement Pack Builder

```bash
# Create builder modules
touch backend/packs/{builder.py,graph_expander.py,entity_extractor.py}

# Test with small seed set (5-10 articles)
wikigr pack build test-tiny --seeds tests/fixtures/tiny_seeds.txt --max-articles 10
```

### Step 5: Run Evaluation on Prototype

```bash
# Build physics-expert pack (or small subset)
wikigr pack build physics-proto --seeds seeds/physics-50.txt --max-articles 500

# Run evaluation
wikigr pack eval physics-proto --questions eval/physics-10.jsonl

# Verify pack beats baselines
# If not, iterate on pack quality before scaling up
```

### Step 6: Implement Distribution

```bash
# Create installer
touch backend/packs/installer.py

# Test install/uninstall
wikigr pack install physics-proto.tar.gz
wikigr pack list
wikigr pack uninstall physics-proto
```

## Critical Implementation Notes

### Architect's Key Recommendation

**PROTOTYPE EVALUATION FIRST** before full implementation. The entire value proposition depends on proving "packs beat web search by 13%". If evaluation shows packs don't improve accuracy, stop before building full infrastructure.

### Minimal Viable Implementation

1. **Week 1**: Evaluation framework + manual test pack (10 articles)
2. **Week 2**: Run evaluation, validate metrics are meaningful
3. **Week 3**: Pack builder for 500-article prototype
4. **Week 4**: Full physics-expert pack if prototype succeeds

### Metrics Validation

The claimed metrics need careful validation:

- **84.7% accuracy** - Is this realistic? May need conservative estimates
- **0.9s latency** - Achievable with hybrid retrieval? May need caching optimization
- **10x expansion** - Verify with actual Wikipedia BFS before claiming

Add conservative estimates or caveats about optimization requirements in documentation.

## Next Steps

1. Read this guide before starting implementation
2. Start with Phase 0 (Evaluation Framework)
3. Build small prototype pack for testing
4. Validate metrics before scaling up
5. Iterate based on evaluation results
