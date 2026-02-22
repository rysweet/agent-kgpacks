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

### Hybrid Search

**GET** `/api/v1/hybrid-search`

Combines semantic similarity (70%) and graph proximity (30%) for richer results.

**Query Parameters:**

| Parameter   | Type   | Required | Default | Description                       |
| ----------- | ------ | -------- | ------- | --------------------------------- |
| `query`     | string | Yes      | -       | Seed article title                |
| `category`  | string | No       | null    | Filter by category                |
| `max_hops`  | int    | No       | 2       | Max graph hops (1-3)              |
| `limit`     | int    | No       | 10      | Max results (1-100)               |

**Response:** Same format as Semantic Search.

**Rate Limit:** 10/minute

**Example:**
```bash
curl "http://localhost:8000/api/v1/hybrid-search?query=Machine+Learning&max_hops=2&limit=10"
```

---

### Chat

**POST** `/api/v1/chat`

Ask natural language questions about the knowledge graph. Supports SSE streaming.

**Request Body:**
```json
{
  "messages": [{"role": "user", "content": "What is quantum entanglement?"}],
  "stream": true
}
```

**Rate Limit:** 5/minute

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "What is machine learning?"}], "stream": false}'
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
      "article_count": 1234
    },
    {
      "name": "Physics",
      "article_count": 892
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
    "message": "Limit must be between 1 and 100"
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
| `INTERNAL_ERROR`      | 500    | Internal server error           |
| `AGENT_UNAVAILABLE`   | 503    | Chat agent not available        |

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

## Rate Limiting

All endpoints are rate-limited per IP address via slowapi:

| Endpoint                | Limit     |
| ----------------------- | --------- |
| `/api/v1/search`        | 10/minute |
| `/api/v1/autocomplete`  | 60/minute |
| `/api/v1/graph`         | 20/minute |
| `/api/v1/hybrid-search` | 10/minute |
| `/api/v1/articles/*`    | 30/minute |
| `/api/v1/categories`    | 30/minute |
| `/api/v1/stats`         | 30/minute |
| `/api/v1/chat`          | 5/minute  |

Rate limiting can be disabled for testing via `WIKIGR_RATE_LIMIT_ENABLED=false`.

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
**Server:** FastAPI 0.115+ + Uvicorn
