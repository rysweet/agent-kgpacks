# ArticleProcessor API Reference

Complete reference for the shared `ArticleProcessor` class used by all content sources.

## ArticleProcessor

Processes articles from any content source (Wikipedia, web, files) with unified entity extraction.

### Class Definition

```python
from backend.kg_construction.article_processor import ArticleProcessor

class ArticleProcessor:
    """
    Shared processor for all content sources.

    Handles:
    - Entity extraction (LLM or heuristic)
    - Relationship identification
    - Vector embedding generation
    - Graph node and edge creation
    """
```

### Constructor

```python
def __init__(
    self,
    conn: kuzu.Connection,
    use_llm: bool = True,
    max_entities: int = 50,
    extract_relationships: bool = True
)
```

**Parameters:**

- `conn` (kuzu.Connection, required): Kuzu database connection
- `use_llm` (bool, default: True): Use LLM extraction (True) or heuristic extraction (False)
- `max_entities` (int, default: 50): Maximum entities to extract per article
- `extract_relationships` (bool, default: True): Extract relationships between entities

**Example:**

```python
import kuzu

db = kuzu.Database("knowledge.db")
conn = kuzu.Connection(db)

# LLM extraction with relationships
processor = ArticleProcessor(conn, use_llm=True, extract_relationships=True)

# Fast heuristic extraction without relationships
processor_fast = ArticleProcessor(conn, use_llm=False, extract_relationships=False)
```

### Methods

#### process_article()

```python
def process_article(
    self,
    title: str,
    content: str,
    url: str
) -> Dict[str, Any]:
    """
    Process a single article and add to knowledge graph.

    Args:
        title: Article title
        content: Article text content
        url: Article URL (for deduplication)

    Returns:
        Dict with extraction statistics:
            {
                "entities_count": int,
                "relationships_count": int,
                "processing_time_ms": float
            }

    Raises:
        ValueError: If title or content is empty
        openai.error.OpenAIError: If LLM extraction fails

    Example:
        >>> stats = processor.process_article(
        ...     title="Azure Kubernetes Service",
        ...     content="AKS is a managed container orchestration...",
        ...     url="https://learn.microsoft.com/en-us/azure/aks/what-is-aks"
        ... )
        >>> print(stats)
        {'entities_count': 42, 'relationships_count': 28, 'processing_time_ms': 3214.5}
    """
```

#### extract_entities()

```python
def extract_entities(
    self,
    title: str,
    content: str
) -> List[Entity]:
    """
    Extract named entities from article content.

    Args:
        title: Article title (used as context)
        content: Article text content

    Returns:
        List of Entity objects with name and type

    Extraction method depends on use_llm setting:
        - use_llm=True: Uses OpenAI to identify entities
        - use_llm=False: Uses regex patterns and NER heuristics

    Example:
        >>> entities = processor.extract_entities(
        ...     title="Azure Kubernetes Service",
        ...     content="AKS is a managed Kubernetes service..."
        ... )
        >>> for entity in entities[:3]:
        ...     print(f"{entity.name} ({entity.type})")
        Azure Kubernetes Service (TECHNOLOGY)
        Kubernetes (TECHNOLOGY)
        Azure (PLATFORM)
    """
```

#### extract_relationships()

```python
def extract_relationships(
    self,
    title: str,
    content: str,
    entities: List[Entity]
) -> List[Relationship]:
    """
    Extract relationships between entities.

    Args:
        title: Article title (context)
        content: Article text content
        entities: Previously extracted entities

    Returns:
        List of Relationship objects with source, relation, target

    Only available when use_llm=True and extract_relationships=True.

    Example:
        >>> relationships = processor.extract_relationships(
        ...     title="Azure Kubernetes Service",
        ...     content="AKS manages Kubernetes clusters...",
        ...     entities=entities
        ... )
        >>> for rel in relationships[:3]:
        ...     print(f"{rel.source} --[{rel.relation}]--> {rel.target}")
        AKS --[MANAGES]--> Kubernetes clusters
        Kubernetes --[RUNS_ON]--> Azure
        AKS --[IS_A]--> managed service
    """
```

#### create_section_node()

```python
def create_section_node(
    self,
    title: str,
    content: str,
    url: str,
    parent_url: Optional[str] = None
) -> str:
    """
    Create Section node in knowledge graph.

    Args:
        title: Section title
        content: Section content (for embedding)
        url: Section URL (unique identifier)
        parent_url: Parent article URL (for hierarchy)

    Returns:
        Section URL (node identifier)

    Creates:
        - Section node with title, URL, embedding
        - PART_OF edge to parent article (if parent_url provided)

    Example:
        >>> section_url = processor.create_section_node(
        ...     title="AKS Overview",
        ...     content="Azure Kubernetes Service provides...",
        ...     url="https://learn.microsoft.com/en-us/azure/aks/what-is-aks#overview",
        ...     parent_url="https://learn.microsoft.com/en-us/azure/aks/what-is-aks"
        ... )
        >>> print(section_url)
        https://learn.microsoft.com/en-us/azure/aks/what-is-aks#overview
    """
```

#### create_entity_node()

```python
def create_entity_node(
    self,
    entity: Entity,
    source_url: str
) -> None:
    """
    Create Entity node in knowledge graph.

    Args:
        entity: Entity object with name and type
        source_url: URL of article containing entity

    Creates:
        - Entity node with name, type
        - MENTIONED_IN edge to source Section

    Handles duplicates by merging (same entity name across articles).

    Example:
        >>> entity = Entity(name="Kubernetes", type="TECHNOLOGY")
        >>> processor.create_entity_node(
        ...     entity=entity,
        ...     source_url="https://learn.microsoft.com/en-us/azure/aks/what-is-aks"
        ... )
    """
```

#### create_relationship_edge()

```python
def create_relationship_edge(
    self,
    relationship: Relationship
) -> None:
    """
    Create relationship edge between entities.

    Args:
        relationship: Relationship object with source, relation, target

    Creates edge between Entity nodes with specified relation type.

    Example:
        >>> rel = Relationship(
        ...     source="AKS",
        ...     relation="MANAGES",
        ...     target="Kubernetes clusters"
        ... )
        >>> processor.create_relationship_edge(rel)
    """
```

## Data Models

### Entity

```python
from dataclasses import dataclass

@dataclass
class Entity:
    """
    Represents a named entity extracted from text.

    Attributes:
        name: Entity name (normalized)
        type: Entity type (PERSON, ORGANIZATION, TECHNOLOGY, CONCEPT, etc.)
    """
    name: str
    type: str
```

**Entity Types:**

- `PERSON` - People, authors, developers
- `ORGANIZATION` - Companies, projects, teams
- `TECHNOLOGY` - Tools, frameworks, services
- `CONCEPT` - Abstract ideas, methodologies
- `LOCATION` - Places, regions, data centers
- `PRODUCT` - Software products, services
- `EVENT` - Conferences, releases, incidents

**Example:**

```python
entities = [
    Entity(name="Azure Kubernetes Service", type="TECHNOLOGY"),
    Entity(name="Microsoft", type="ORGANIZATION"),
    Entity(name="containerization", type="CONCEPT")
]
```

### Relationship

```python
from dataclasses import dataclass

@dataclass
class Relationship:
    """
    Represents a semantic relationship between entities.

    Attributes:
        source: Source entity name
        relation: Relationship type (verb-like)
        target: Target entity name
    """
    source: str
    relation: str
    target: str
```

**Common Relations:**

- `IS_A` - Type/category relationship
- `PART_OF` - Component relationship
- `USES` - Dependency relationship
- `MANAGES` - Control relationship
- `PROVIDES` - Service relationship
- `RUNS_ON` - Platform relationship
- `DEVELOPED_BY` - Authorship relationship

**Example:**

```python
relationships = [
    Relationship(source="AKS", relation="IS_A", target="managed service"),
    Relationship(source="AKS", relation="MANAGES", target="Kubernetes"),
    Relationship(source="Kubernetes", relation="RUNS_ON", target="Azure")
]
```

## LLM Extraction Pipeline

When `use_llm=True`, extraction follows this pipeline:

### 1. Entity Extraction Prompt

```
Given the following article, extract all named entities:

Title: {title}
Content: {content}

Extract entities in these categories:
- PERSON (people, authors)
- ORGANIZATION (companies, projects)
- TECHNOLOGY (tools, frameworks, services)
- CONCEPT (abstract ideas)
- LOCATION (places, regions)
- PRODUCT (software products)

Return as JSON array: [{"name": "...", "type": "..."}]
```

### 2. Relationship Extraction Prompt

```
Given these entities from the article, identify relationships:

Entities: {entities}
Content: {content}

Extract relationships as JSON array:
[{"source": "...", "relation": "...", "target": "..."}]

Use relation types: IS_A, PART_OF, USES, MANAGES, PROVIDES, RUNS_ON
```

### 3. Entity Normalization

After extraction, entities are normalized:

```python
def normalize_entity(name: str) -> str:
    """
    Normalize entity name for consistency.

    - Remove extra whitespace
    - Title case for proper nouns
    - Expand common abbreviations
    - Remove parenthetical notes

    Example:
        >>> normalize_entity("azure kubernetes service (AKS)")
        "Azure Kubernetes Service"
    """
```

### 4. Vector Embedding

Each entity and section gets an embedding:

```python
from openai import OpenAI

client = OpenAI()
response = client.embeddings.create(
    model="text-embedding-ada-002",
    input=text
)
embedding = response.data[0].embedding
```

## Heuristic Extraction (use_llm=False)

When LLM extraction is disabled, uses pattern-based extraction:

### Entity Patterns

```python
ENTITY_PATTERNS = {
    "TECHNOLOGY": r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b",  # Proper nouns
    "CONCEPT": r"\b(?:pattern|principle|methodology|approach)\b",
    "ORGANIZATION": r"\b(?:Microsoft|Google|Amazon|IBM)\b",
}
```

### Relationship Heuristics

- Co-occurrence in same sentence → weak relationship
- Verb phrases between entities → relation type
- No LLM means fewer, less accurate relationships

**Performance:**

- 10x faster than LLM extraction
- 50-70% entity recall vs LLM
- Minimal relationship extraction

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | None (required) |
| `OPENAI_MODEL` | LLM model | `gpt-4-turbo-preview` |
| `LLM_TEMPERATURE` | Sampling temperature | `0.0` |
| `LLM_MAX_RETRIES` | Retry attempts | `3` |
| `LLM_RETRY_DELAY` | Retry delay (seconds) | `1.0` |
| `EMBEDDING_MODEL` | Embedding model | `text-embedding-ada-002` |

### Constructor Parameters

```python
# High-quality extraction (default)
processor = ArticleProcessor(conn, use_llm=True, max_entities=50, extract_relationships=True)

# Fast extraction for large crawls
processor = ArticleProcessor(conn, use_llm=True, max_entities=30, extract_relationships=False)

# Heuristic extraction (no API cost)
processor = ArticleProcessor(conn, use_llm=False, max_entities=100, extract_relationships=False)
```

## Performance Characteristics

### Time Complexity

- Entity extraction: O(n) where n = content length
- Relationship extraction: O(e²) where e = entity count
- Graph insertion: O(e + r) where r = relationship count

### API Cost (LLM Extraction)

Per article with GPT-4-turbo-preview:

| Operation | Tokens | Cost |
|-----------|--------|------|
| Entity extraction | ~2,000 | $0.02 |
| Relationship extraction | ~1,500 | $0.015 |
| Embeddings (50 entities) | ~500 | $0.0001 |
| **Total per article** | ~4,000 | **$0.035** |

### Benchmarks

Measured on Azure AKS documentation article (3,500 words):

| Configuration | Entities | Relationships | Time | Cost |
|---------------|----------|---------------|------|------|
| LLM + relationships | 42 | 28 | 3.2s | $0.035 |
| LLM - relationships | 42 | 0 | 1.8s | $0.020 |
| Heuristic | 28 | 0 | 0.3s | $0.0001 |

## Error Handling

### Common Exceptions

```python
# Empty content
try:
    processor.process_article(title="", content="", url="...")
except ValueError as e:
    print(f"Invalid input: {e}")

# LLM failure
try:
    processor.extract_entities(title, content)
except openai.error.RateLimitError:
    print("Rate limit exceeded, retrying...")

# Database error
try:
    processor.create_entity_node(entity, url)
except kuzu.Exception as e:
    print(f"Database error: {e}")
```

### Retry Logic

LLM calls automatically retry on failure:

```python
@retry(
    max_attempts=int(os.getenv("LLM_MAX_RETRIES", "3")),
    delay=float(os.getenv("LLM_RETRY_DELAY", "1.0")),
    backoff=2.0
)
def call_llm(prompt: str) -> str:
    return openai_client.chat.completions.create(...)
```

## Integration Examples

### With WebContentSource

```python
from backend.sources.web_content_source import WebContentSource
from backend.kg_construction.article_processor import ArticleProcessor
import kuzu

# Setup
db = kuzu.Database("azure_docs.db")
conn = kuzu.Connection(db)
processor = ArticleProcessor(conn, use_llm=True)

# Create source
source = WebContentSource(
    url="https://learn.microsoft.com/en-us/azure/aks/what-is-aks",
    max_depth=2,
    max_links=25
)

# Process articles
for article in source.get_articles():
    stats = processor.process_article(
        title=article.title,
        content=article.content,
        url=article.url
    )
    print(f"Processed {article.title}: {stats['entities_count']} entities")
```

### With WikipediaContentSource

```python
from backend.sources.wikipedia_content_source import WikipediaContentSource

source = WikipediaContentSource(title="Kubernetes")

for article in source.get_articles():
    processor.process_article(
        title=article.title,
        content=article.content,
        url=article.url
    )
```

### Batch Processing

```python
from concurrent.futures import ThreadPoolExecutor

def process_url(url: str) -> Dict[str, Any]:
    source = WebContentSource(url=url)
    for article in source.get_articles():
        return processor.process_article(article.title, article.content, article.url)

urls = [
    "https://example.com/page1",
    "https://example.com/page2",
    "https://example.com/page3"
]

with ThreadPoolExecutor(max_workers=5) as executor:
    results = list(executor.map(process_url, urls))

print(f"Processed {len(results)} articles")
```

## Related Documentation

- [Web Content Source API Reference](./web-content-source.md)
- [Getting Started with Web Sources](../tutorials/web-sources-getting-started.md)
- [How to Configure LLM Extraction](../howto/configure-llm-extraction.md)
- [Understanding ContentSource Architecture](../concepts/content-source-design.md)
