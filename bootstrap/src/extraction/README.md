# Extraction Module

LLM-based knowledge extraction from Wikipedia articles using Claude.

## Overview

The extraction module uses the Anthropic API to extract structured knowledge
(entities, relationships, and key facts) from Wikipedia article text.

## Public Interface

- `LLMExtractor`: Main extraction class
- `Entity`, `Relationship`, `ExtractionResult`: Data models
- `get_extractor()`: Singleton accessor

## Usage

```python
from bootstrap.src.extraction.llm_extractor import LLMExtractor

extractor = LLMExtractor()
result = extractor.extract_from_article(title, sections)
print(result.entities, result.relationships, result.key_facts)
```

Requires `ANTHROPIC_API_KEY` environment variable.
