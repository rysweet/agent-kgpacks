# Embeddings Module

**Status:** ✅ Complete

Vector embedding generation for semantic search in Wikipedia articles.

---

## Module Contract

### Purpose

Generate 384-dimensional vector embeddings from text using the `paraphrase-MiniLM-L3-v2` model.

### Public Interface

```python
from embeddings.generator import EmbeddingGenerator

# Initialize
gen = EmbeddingGenerator()

# Generate embeddings
texts = ["Machine learning intro", "Deep learning basics"]
embeddings = gen.generate(texts, batch_size=32, show_progress=True)
# Returns: numpy.ndarray of shape (N, 384)
```

### Dependencies

- `sentence-transformers` - Model loading and inference
- `torch` - GPU detection and tensor operations
- `numpy` - Array operations

---

## Components

### EmbeddingGenerator

**Location:** `generator.py`

**Responsibility:** Generate vector embeddings for text strings.

**Methods:**

#### `__init__(model_name='paraphrase-MiniLM-L3-v2', use_gpu=None)`

Initialize the embedding generator.

**Parameters:**
- `model_name` (str): Model from sentence-transformers. Default is `paraphrase-MiniLM-L3-v2`.
- `use_gpu` (bool|None): Force GPU (True), CPU (False), or auto-detect (None).

**Behavior:**
- Auto-detects CUDA availability if `use_gpu=None`
- Downloads model on first run (cached afterwards)
- Loads model to specified device (CPU/GPU)

#### `generate(texts, batch_size=32, show_progress=False)`

Generate embeddings for text list.

**Parameters:**
- `texts` (list[str]): Text strings to embed
- `batch_size` (int): Texts per batch (default 32)
- `show_progress` (bool): Show progress bar

**Returns:**
- `numpy.ndarray`: Shape (N, 384) where N = len(texts)

**Raises:**
- `ValueError`: If texts is empty

**Performance:**
- CPU: ~1055 texts/sec
- GPU: ~10,000-20,000 texts/sec (estimated)
- Memory: ~2.6GB for 900K vectors

---

## Model Selection

**Model:** `paraphrase-MiniLM-L3-v2`

**Why this model:**
- **Fastest:** 1055 texts/sec (63% faster than alternatives)
- **Compact:** 384 dimensions (efficient storage and queries)
- **Sufficient quality:** 65-75% precision for semantic search
- **Memory efficient:** 2.6GB for 30K articles

**See:** `bootstrap/docs/embedding-model-choice.md` for full benchmarks and rationale.

---

## Usage Examples

### Basic Usage

```python
from embeddings.generator import EmbeddingGenerator

# Initialize (auto-detect GPU)
gen = EmbeddingGenerator()

# Generate embeddings
texts = ["Python programming", "JavaScript development"]
embeddings = gen.generate(texts)

print(embeddings.shape)  # (2, 384)
```

### Batch Processing

```python
# Process large dataset with progress bar
large_texts = [f"Article section {i}" for i in range(10000)]
embeddings = gen.generate(
    large_texts,
    batch_size=32,
    show_progress=True
)
```

### Force CPU/GPU

```python
# Force CPU (for testing)
gen_cpu = EmbeddingGenerator(use_gpu=False)

# Force GPU (if available)
gen_gpu = EmbeddingGenerator(use_gpu=True)
```

### Cosine Similarity

```python
import numpy as np

texts = ["Machine learning", "Deep learning", "Cooking recipes"]
embeddings = gen.generate(texts)

# Calculate cosine similarity between first two
e1, e2 = embeddings[0], embeddings[1]
similarity = np.dot(e1, e2) / (np.linalg.norm(e1) * np.linalg.norm(e2))
print(f"Similarity: {similarity:.4f}")  # Expected: 0.6-0.8
```

---

## Testing

### Run Tests

```bash
cd bootstrap
python3 src/embeddings/generator.py
```

### Test Coverage

The built-in test validates:
- Model loads successfully
- Embeddings have correct shape (N, 384)
- Embeddings are non-zero
- L2 norms are reasonable (~1.0)
- Embeddings differ (variance check)
- Cosine similarity works for similar texts
- Error handling (empty list)

---

## Performance

### Throughput

| Hardware | Texts/Sec | Time for 30K articles |
|----------|-----------|----------------------|
| CPU      | 1,055     | 14 minutes           |
| GPU      | 10,000+   | 1-2 minutes (est.)   |

### Memory

| Dataset Size | Vector Storage | Total RAM |
|--------------|----------------|-----------|
| 1K articles  | 87 MB          | <1 GB     |
| 10K articles | 870 MB         | ~1.5 GB   |
| 30K articles | 2.6 GB         | ~3 GB     |

---

## Error Handling

**Empty text list:**
```python
gen.generate([])  # Raises ValueError
```

**CUDA not available:**
```python
gen = EmbeddingGenerator(use_gpu=True)
# Falls back to CPU if CUDA unavailable
```

---

## Future Enhancements

**Not implemented (intentionally):**
- Model caching across instances - Use single instance
- Async generation - Use batch processing instead
- Multi-GPU support - Single GPU sufficient for 30K articles
- Embedding normalization - Model already returns normalized vectors

**Potential upgrades:**
- Switch to `all-MiniLM-L6-v2` if quality insufficient (5-10% better)
- Switch to `all-mpnet-base-v2` if quality critical (768 dims, 8x slower)

---

## Integration Points

**Used by:**
- `bootstrap/src/wikipedia/` - Embedding Wikipedia article sections
- `bootstrap/src/database/` - Storing embeddings in Kuzu vector index

**Uses:**
- `sentence-transformers` - Pre-trained transformer models
- `torch` - GPU acceleration

---

## References

- **Model card:** https://huggingface.co/sentence-transformers/paraphrase-MiniLM-L3-v2
- **sentence-transformers:** https://www.sbert.net/
- **Benchmark results:** `bootstrap/docs/embedding-model-choice.md`
