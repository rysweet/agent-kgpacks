# WikiGR Visualization API Documentation

RESTful API for Wikipedia knowledge graph queries and visualization data.

## Base URL

```
Development: http://localhost:8000
Production:  https://wikigr.example.com/api
```

## Authentication

**None required** for read-only operations. All endpoints are public.

## Endpoints

### Health Check

**GET** `/health`

Check API server status.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "database": "connected",
  "timestamp": "2026-02-10T15:30:00Z"
}
```

**Status Codes:**
- `200`: Service healthy
- `503`: Service unavailable

**Example:**
```bash
curl http://localhost:8000/health
```

---

### Semantic Search

**GET** `/api/v1/search`

Find articles semantically similar to a query.

**Query Parameters:**

| Parameter   | Type   | Required | Default | Description                       |
| ----------- | ------ | -------- | ------- | --------------------------------- |
| `query`     | string | Yes      | -       | Search query (article title)      |
| `category`  | string | No       | null    | Filter by category                |
| `limit`     | int    | No       | 10      | Max results (1-100)               |
| `threshold` | float  | No       | 0.0     | Min similarity score (0.0-1.0)    |

**Response:**
```json
{
  "query": "Machine Learning",
  "results": [
    {
      "article": "Deep Learning",
      "similarity": 0.89,
      "category": "Computer Science",
      "word_count": 4523,
      "summary": "Deep learning is a subset of machine learning..."
    },
    {
      "article": "Neural Networks",
      "similarity": 0.87,
      "category": "Computer Science",
      "word_count": 3891,
      "summary": "Neural networks are computing systems..."
    }
  ],
  "total": 2,
  "execution_time_ms": 45
}
```

**Status Codes:**
- `200`: Success
- `400`: Invalid parameters
- `404`: Query article not found
- `500`: Server error

**Example:**
```bash
# Basic search
curl "http://localhost:8000/api/v1/search?query=Machine+Learning&limit=5"

# With filters
curl "http://localhost:8000/api/v1/search?query=Quantum+Mechanics&category=Physics&threshold=0.7"
```

---

### Graph Data

**GET** `/api/v1/graph`

Retrieve graph structure around seed article.

**Query Parameters:**

| Parameter  | Type   | Required | Default | Description                    |
| ---------- | ------ | -------- | ------- | ------------------------------ |
| `article`  | string | Yes      | -       | Seed article title             |
| `depth`    | int    | No       | 2       | Max hops from seed (1-3)       |
| `limit`    | int    | No       | 50      | Max nodes to return (1-200)    |
| `category` | string | No       | null    | Filter by category             |

**Response:**
```json
{
  "seed": "Machine Learning",
  "nodes": [
    {
      "id": "Machine Learning",
      "title": "Machine Learning",
      "category": "Computer Science",
      "word_count": 5234,
      "depth": 0,
      "links_count": 42,
      "summary": "Machine learning is the study of..."
    },
    {
      "id": "Deep Learning",
      "title": "Deep Learning",
      "category": "Computer Science",
      "word_count": 4523,
      "depth": 1,
      "links_count": 38,
      "summary": "Deep learning is a subset..."
    }
  ],
  "edges": [
    {
      "source": "Machine Learning",
      "target": "Deep Learning",
      "type": "internal",
      "weight": 1.0
    },
    {
      "source": "Machine Learning",
      "target": "Neural Networks",
      "type": "internal",
      "weight": 0.95
    }
  ],
  "total_nodes": 2,
  "total_edges": 2,
  "execution_time_ms": 67
}
```

**Status Codes:**
- `200`: Success
- `400`: Invalid parameters
- `404`: Seed article not found
- `500`: Server error

**Example:**
```bash
# Basic graph
curl "http://localhost:8000/api/v1/graph?article=Machine+Learning"

# With depth limit
curl "http://localhost:8000/api/v1/graph?article=Quantum+Mechanics&depth=1&limit=25"
```

---

### Hybrid Query

**POST** `/api/v1/hybrid`

Combine semantic search and graph traversal.

**Request Body:**
```json
{
  "query": "Machine Learning",
  "category": "Computer Science",
  "depth": 2,
  "limit": 10,
  "semantic_weight": 0.7,
  "graph_weight": 0.3,
  "threshold": 0.5
}
```

**Parameters:**

| Parameter         | Type   | Required | Default | Description                       |
| ----------------- | ------ | -------- | ------- | --------------------------------- |
| `query`           | string | Yes      | -       | Search query                      |
| `category`        | string | No       | null    | Category filter                   |
| `depth`           | int    | No       | 2       | Graph traversal depth (1-3)       |
| `limit`           | int    | No       | 10      | Max results (1-100)               |
| `semantic_weight` | float  | No       | 0.7     | Semantic score weight (0.0-1.0)   |
| `graph_weight`    | float  | No       | 0.3     | Graph proximity weight (0.0-1.0)  |
| `threshold`       | float  | No       | 0.5     | Min combined score (0.0-1.0)      |

**Response:**
```json
{
  "query": "Machine Learning",
  "results": [
    {
      "article": "Deep Learning",
      "semantic_score": 0.89,
      "graph_distance": 1,
      "combined_score": 0.82,
      "category": "Computer Science",
      "summary": "Deep learning is..."
    }
  ],
  "total": 1,
  "execution_time_ms": 89
}
```

**Status Codes:**
- `200`: Success
- `400`: Invalid parameters
- `404`: Query article not found
- `422`: Validation error (weights don't sum to 1.0)
- `500`: Server error

**Example:**
```bash
curl -X POST http://localhost:8000/api/v1/hybrid \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Machine Learning",
    "category": "Computer Science",
    "semantic_weight": 0.8,
    "graph_weight": 0.2
  }'
```

---

### Article Details

**GET** `/api/v1/articles/{title}`

Get detailed information about a specific article.

**Path Parameters:**
- `title`: URL-encoded article title

**Response:**
```json
{
  "title": "Machine Learning",
  "category": "Computer Science",
  "word_count": 5234,
  "sections": [
    {
      "title": "Overview",
      "content": "Machine learning is the study of...",
      "word_count": 342,
      "level": 2
    },
    {
      "title": "History",
      "content": "The term machine learning was coined...",
      "word_count": 456,
      "level": 2
    }
  ],
  "links": [
    "Deep Learning",
    "Neural Networks",
    "Artificial Intelligence"
  ],
  "backlinks": [
    "Artificial Intelligence",
    "Data Science"
  ],
  "categories": [
    "Computer Science",
    "Artificial Intelligence",
    "Machine Learning"
  ],
  "wikipedia_url": "https://en.wikipedia.org/wiki/Machine_Learning",
  "last_updated": "2026-02-10T12:00:00Z"
}
```

**Status Codes:**
- `200`: Success
- `404`: Article not found
- `500`: Server error

**Example:**
```bash
curl "http://localhost:8000/api/v1/articles/Machine%20Learning"
```

---

### Category List

**GET** `/api/v1/categories`

List all available categories with article counts.

**Response:**
```json
{
  "categories": [
    {
      "name": "Computer Science",
      "article_count": 1234,
      "subcategories": [
        "Artificial Intelligence",
        "Programming Languages",
        "Algorithms"
      ]
    },
    {
      "name": "Physics",
      "article_count": 892,
      "subcategories": [
        "Quantum Mechanics",
        "Relativity",
        "Thermodynamics"
      ]
    }
  ],
  "total": 2
}
```

**Status Codes:**
- `200`: Success
- `500`: Server error

**Example:**
```bash
curl http://localhost:8000/api/v1/categories
```

---

### Statistics

**GET** `/api/v1/stats`

Database statistics and metrics.

**Response:**
```json
{
  "articles": {
    "total": 30000,
    "by_category": {
      "Computer Science": 1234,
      "Physics": 892,
      "Mathematics": 756
    },
    "by_depth": {
      "0": 10,
      "1": 245,
      "2": 29745
    }
  },
  "sections": {
    "total": 450000,
    "avg_per_article": 15
  },
  "links": {
    "total": 125000,
    "avg_per_article": 4.2
  },
  "database": {
    "size_mb": 2847,
    "last_updated": "2026-02-10T10:00:00Z"
  },
  "performance": {
    "avg_query_time_ms": 45,
    "p95_query_time_ms": 120,
    "p99_query_time_ms": 250
  }
}
```

**Status Codes:**
- `200`: Success
- `500`: Server error

**Example:**
```bash
curl http://localhost:8000/api/v1/stats
```

---

### Autocomplete

**GET** `/api/v1/autocomplete`

Article title suggestions for search input.

**Query Parameters:**

| Parameter | Type   | Required | Default | Description                  |
| --------- | ------ | -------- | ------- | ---------------------------- |
| `q`       | string | Yes      | -       | Partial query (min 2 chars)  |
| `limit`   | int    | No       | 10      | Max suggestions (1-20)       |

**Response:**
```json
{
  "query": "mach",
  "suggestions": [
    {
      "title": "Machine Learning",
      "category": "Computer Science",
      "match_type": "prefix"
    },
    {
      "title": "Machiavelli",
      "category": "History",
      "match_type": "prefix"
    },
    {
      "title": "Machinery",
      "category": "Engineering",
      "match_type": "prefix"
    }
  ],
  "total": 3
}
```

**Status Codes:**
- `200`: Success
- `400`: Query too short (< 2 chars)
- `500`: Server error

**Example:**
```bash
curl "http://localhost:8000/api/v1/autocomplete?q=mach&limit=5"
```

---

## Error Responses

All errors follow this format:

```json
{
  "error": {
    "code": "INVALID_PARAMETER",
    "message": "Limit must be between 1 and 100",
    "details": {
      "parameter": "limit",
      "provided": 500,
      "allowed": "1-100"
    }
  },
  "timestamp": "2026-02-10T15:30:00Z"
}
```

**Error Codes:**

| Code                  | Status | Description                     |
| --------------------- | ------ | ------------------------------- |
| `INVALID_PARAMETER`   | 400    | Parameter validation failed     |
| `MISSING_PARAMETER`   | 400    | Required parameter missing      |
| `NOT_FOUND`           | 404    | Article/resource not found      |
| `VALIDATION_ERROR`    | 422    | Request body validation failed  |
| `RATE_LIMIT_EXCEEDED` | 429    | Too many requests               |
| `SERVER_ERROR`        | 500    | Internal server error           |
| `DATABASE_ERROR`      | 500    | Database connection/query error |

---

## Rate Limiting

**Limits:**
- 100 requests per minute per IP
- 1000 requests per hour per IP

**Headers:**
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1644508800
```

**Exceeded response:**
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Try again in 32 seconds.",
    "retry_after": 32
  }
}
```

**Status:** `429 Too Many Requests`

---

## CORS

**Allowed origins:**
- Development: `http://localhost:5173`
- Production: `https://wikigr.example.com`

**Headers:**
```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST, OPTIONS
Access-Control-Allow-Headers: Content-Type
```

---

## Compression

**Supported:**
- gzip
- br (Brotli)

**Request header:**
```
Accept-Encoding: gzip, br
```

**Response header:**
```
Content-Encoding: gzip
```

**Size reduction:** ~70% for JSON responses

---

## Caching

**Cache-Control headers:**

| Endpoint        | Cache-Control                 | Notes                  |
| --------------- | ----------------------------- | ---------------------- |
| `/health`       | `no-cache`                    | Always fresh           |
| `/api/v1/search`| `private, max-age=3600`       | 1 hour cache           |
| `/api/v1/graph` | `private, max-age=3600`       | 1 hour cache           |
| `/api/v1/stats` | `public, max-age=300`         | 5 minute cache         |
| `/api/v1/articles/*` | `public, max-age=86400` | 24 hour cache          |

**ETag support:**
```
ETag: "33a64df551425fcc55e4d42a148795d9f25f89d4"
If-None-Match: "33a64df551425fcc55e4d42a148795d9f25f89d4"
```

**Response:** `304 Not Modified` if content unchanged

---

## WebSocket API (Real-time Updates)

**Endpoint:** `ws://localhost:8000/ws/graph`

**Connect:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/graph');

ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'subscribe',
    article: 'Machine Learning'
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Graph update:', data);
};
```

**Messages:**

**Subscribe:**
```json
{
  "type": "subscribe",
  "article": "Machine Learning",
  "depth": 2
}
```

**Update:**
```json
{
  "type": "node_added",
  "node": {
    "id": "Deep Learning",
    "title": "Deep Learning",
    "category": "Computer Science"
  }
}
```

**Unsubscribe:**
```json
{
  "type": "unsubscribe"
}
```

---

## Performance Benchmarks

**Hardware:** 8 vCPU, 16 GB RAM, SSD storage

| Endpoint           | P50  | P95  | P99  | Notes             |
| ------------------ | ---- | ---- | ---- | ----------------- |
| `/api/v1/search`   | 45ms | 120ms| 250ms| 30K articles      |
| `/api/v1/graph`    | 67ms | 180ms| 400ms| Depth=2, Limit=50 |
| `/api/v1/hybrid`   | 89ms | 220ms| 500ms| Combined query    |
| `/api/v1/articles` | 12ms | 35ms | 80ms | Single article    |

---

## Client Libraries

**Python:**
```python
from wikigr_client import WikiGRClient

client = WikiGRClient(base_url="http://localhost:8000")

# Search
results = client.search("Machine Learning", limit=10)

# Graph
graph = client.graph("Machine Learning", depth=2)

# Article details
article = client.get_article("Machine Learning")
```

**JavaScript/TypeScript:**
```typescript
import { WikiGRClient } from 'wikigr-client';

const client = new WikiGRClient('http://localhost:8000');

// Search
const results = await client.search('Machine Learning', { limit: 10 });

// Graph
const graph = await client.graph('Machine Learning', { depth: 2 });
```

**Installation:**
```bash
# Python
pip install wikigr-client

# JavaScript
npm install wikigr-client
```

---

## Development

### Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Start server
uvicorn backend.main:app --reload --port 8000

# Open API docs
http://localhost:8000/docs
```

### Testing API

```bash
# Run tests
pytest backend/tests/

# With coverage
pytest --cov=backend backend/tests/

# Load testing
locust -f backend/tests/load_test.py
```

### OpenAPI Spec

**Interactive docs:** http://localhost:8000/docs

**ReDoc:** http://localhost:8000/redoc

**OpenAPI JSON:** http://localhost:8000/openapi.json

---

**API Version:** 1.0.0
**Updated:** February 2026
**Server:** FastAPI 0.109.0 + Uvicorn
