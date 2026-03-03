# Database Module

Loads Wikipedia articles into the LadybugDB graph database.

## Public Interface

```python
from bootstrap.src.database import ArticleLoader

loader = ArticleLoader("data/wikigr.db")
success, error = loader.load_article("Python (programming language)")
```

## Components

- `ArticleLoader` - Integrates Wikipedia API, parser, and embeddings to load articles transactionally

## Dependencies

- `bootstrap.src.wikipedia` (fetch and parse)
- `bootstrap.src.embeddings` (generate vectors)
- `real_ladybug` (aliased as `kuzu`) for LadybugDB database
