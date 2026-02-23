# Sources

Pluggable content sources for knowledge graph construction.

```python
from bootstrap.src.sources import WikipediaContentSource, WebContentSource

# Wikipedia
wiki = WikipediaContentSource()
article = wiki.fetch_article("Machine Learning")

# Generic web
web = WebContentSource()
article = web.fetch_article("https://learn.microsoft.com/en-us/azure/aks/what-is-aks")
```

## Implementations

- `WikipediaContentSource` - Wraps existing Wikipedia API client
- `WebContentSource` - Fetches any URL, converts HTML to markdown, extracts sections/links
