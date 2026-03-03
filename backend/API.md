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

### Chat (blocking)

**POST** `/api/v1/chat`

Ask a natural language question about the knowledge graph.
Returns a complete JSON response once the agent finishes synthesizing.

**Rate Limit:** 5/minute

**Request Body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `question` | string | Yes | — | Natural language question (1–500 chars) |
| `pack` | string\|null | No | null | Pack name to query (e.g. `"dotnet-expert"`). Uses default graph when omitted |
| `max_results` | int | No | 10 | Maximum vector-search results (1–50) |

**Example request:**
```json
{
  "question": "What is goroutine scheduling?",
  "pack": "go-expert",
  "max_results": 10
}
```

**Response:**
```json
{
  "answer": "Go uses an M:N scheduling model where many goroutines are multiplexed...",
  "sources": ["runtime_scheduling", "goroutines", "channel_internals"],
  "query_type": "vector_search",
  "execution_time_ms": 1240.3
}
```

**Response fields:**

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | Synthesized natural-language answer |
| `sources` | string[] | Article titles used as evidence |
| `query_type` | string | `vector_search` \| `confidence_gated_fallback` \| `vector_fallback` |
| `execution_time_ms` | float | Total wall-clock time for the request |

**Status Codes:**
- `200`: Success
- `400`: Invalid request body (validation error or invalid pack name format)
- `404`: Requested pack not found (`PACK_NOT_FOUND`)
- `429`: Rate limit exceeded
- `500`: Agent error (`AGENT_ERROR`)
- `503`: `ANTHROPIC_API_KEY` not configured (`AGENT_UNAVAILABLE`)

**Example:**
```bash
# Query the default knowledge graph
curl -X POST "http://localhost:8000/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is machine learning?"}'

# Query a specific pack
curl -X POST "http://localhost:8000/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{"question": "How do channels work?", "pack": "go-expert", "max_results": 5}'
```

---

### Chat (streaming)

**GET** `/api/v1/chat/stream`

Stream a chat response via Server-Sent Events (SSE).
The connection stays open while the agent queries the knowledge graph,
then delivers events in order: `sources` → `token` → `done` (or `error`).

**Rate Limit:** 5/minute (shared with POST /api/v1/chat)

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `question` | string | Yes | — | Natural language question (1–500 chars) |
| `max_results` | int | No | 10 | Maximum vector-search results (1–50) |

**SSE Event Types:**

| Event type | `data` field | Description |
|------------|-------------|-------------|
| `sources` | JSON array of strings | Article titles used as evidence (sent before the answer) |
| `token` | Plain text string | Complete answer text (single event, not incremental tokens) |
| `done` | JSON object | `{"query_type": "...", "execution_time_ms": 1240.3}` |
| `error` | Exception class name string | Emitted if the agent raises an exception |

**Status Codes:**
- `200`: SSE stream opened (errors during generation appear as `error` events)
- `429`: Rate limit exceeded
- `503`: `ANTHROPIC_API_KEY` not configured

**Example – curl:**
```bash
curl -N "http://localhost:8000/api/v1/chat/stream?question=What+is+goroutine+scheduling%3F"
```

**Example output:**
```
event: sources
data: ["runtime_scheduling","goroutines","channel_internals"]

event: token
data: Go uses an M:N scheduling model where many goroutines are multiplexed onto a smaller number of OS threads...

event: done
data: {"query_type": "vector_search", "execution_time_ms": 1240.3}
```

**Example – JavaScript (EventSource):**
```javascript
const url = new URL('http://localhost:8000/api/v1/chat/stream');
url.searchParams.set('question', 'What is goroutine scheduling?');

const es = new EventSource(url);

es.addEventListener('sources', e => {
  const sources = JSON.parse(e.data);
  console.log('Sources:', sources);
});

es.addEventListener('token', e => {
  process.stdout.write(e.data);
});

es.addEventListener('done', e => {
  const meta = JSON.parse(e.data);
  console.log('\nDone:', meta);
  es.close();
});

es.addEventListener('error', e => {
  console.error('Agent error:', e.data);
  es.close();
});
```

**Example – Python (sseclient):**
```python
import json
import sseclient
import requests

url = 'http://localhost:8000/api/v1/chat/stream'
params = {'question': 'What is goroutine scheduling?', 'max_results': 5}

response = requests.get(url, params=params, stream=True)
client = sseclient.SSEClient(response)

for event in client.events():
    if event.event == 'sources':
        print('Sources:', json.loads(event.data))
    elif event.event == 'token':
        print('Answer:', event.data)
    elif event.event == 'done':
        print('Meta:', json.loads(event.data))
        break
    elif event.event == 'error':
        print('Error:', event.data)
        break
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

| Code                  | Status | Description                                          |
| --------------------- | ------ | ---------------------------------------------------- |
| `INVALID_PARAMETER`   | 400    | Parameter validation failed                          |
| `MISSING_PARAMETER`   | 400    | Required parameter missing                           |
| `INVALID_PACK_NAME`   | 400    | Pack name contains illegal characters                |
| `NOT_FOUND`           | 404    | Article/resource not found                           |
| `PACK_NOT_FOUND`      | 404    | Requested knowledge pack does not exist on this server |
| `INTERNAL_ERROR`      | 500    | Internal server error                                |
| `AGENT_ERROR`         | 500    | KnowledgeGraphAgent raised an exception              |
| `AGENT_UNAVAILABLE`   | 503    | `ANTHROPIC_API_KEY` not configured                   |

---

## CORS

**Allowed origins** (configured in `backend/config.py`, overridable via `WIKIGR_CORS_ORIGINS`):
- `http://localhost:3000`
- `http://localhost:5173`
- `http://127.0.0.1:3000`
- `http://127.0.0.1:5173`

**Headers (when request Origin matches an allowed origin):**
```
Access-Control-Allow-Origin: <matched origin>
Access-Control-Allow-Methods: GET, POST, OPTIONS
Access-Control-Allow-Headers: Content-Type
```

---

## Rate Limiting

All endpoints are rate-limited per IP address via slowapi:

| Endpoint                  | Limit     |
| ------------------------- | --------- |
| `/api/v1/search`          | 10/minute |
| `/api/v1/autocomplete`    | 60/minute |
| `/api/v1/graph`           | 20/minute |
| `/api/v1/hybrid-search`   | 10/minute |
| `/api/v1/articles/*`      | 30/minute |
| `/api/v1/categories`      | 30/minute |
| `/api/v1/stats`           | 30/minute |
| `POST /api/v1/chat`       | 5/minute  |
| `GET /api/v1/chat/stream` | 5/minute  |

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
