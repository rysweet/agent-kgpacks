# Chat API Reference

The Chat API exposes the `KnowledgeGraphAgent` to HTTP clients.
Two endpoints are available: a blocking JSON endpoint for simple integrations and
a streaming SSE endpoint for browser UIs that want to show progressive results.

Both endpoints share the same rate limit (5 requests/minute per IP).

---

## POST /api/v1/chat

Ask a natural language question and receive a single JSON response.

### Request

```
POST /api/v1/chat
Content-Type: application/json
```

**Body fields:**

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `question` | string | Yes | 1–500 chars | Natural language question |
| `pack` | string \| null | No | Pattern `^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$` | Knowledge pack to query. Uses default graph when omitted |
| `max_results` | integer | No | 1–50, default 10 | Maximum number of vector-search results |

### Response

```
HTTP 200 OK
Content-Type: application/json
```

```json
{
  "answer": "Go uses an M:N scheduling model...",
  "sources": ["runtime_scheduling", "goroutines"],
  "query_type": "vector_search",
  "execution_time_ms": 1240.3
}
```

**Response fields:**

| Field | Type | Description |
|-------|------|-------------|
| `answer` | string | Synthesized natural-language answer |
| `sources` | string[] | Article titles used as evidence by the agent |
| `query_type` | string | How the query was resolved. See [query_type values](#query_type-values) |
| `execution_time_ms` | float | Total wall-clock time for this request, in milliseconds |

### query_type values

| Value | Meaning |
|-------|---------|
| `vector_search` | Normal path — pack content retrieved and used for synthesis |
| `confidence_gated_fallback` | Confidence gate fired — Claude answered without pack context (similarity below threshold) |
| `vector_fallback` | Vector search returned no results at all |

### Error responses

| HTTP status | Error code | When |
|-------------|------------|------|
| 400 | `INVALID_PACK_NAME` | `pack` field contains illegal characters |
| 404 | `PACK_NOT_FOUND` | Named pack does not exist on this server |
| 429 | — | Rate limit exceeded (slowapi default body) |
| 500 | `AGENT_ERROR` | The agent raised an unhandled exception |
| 503 | `AGENT_UNAVAILABLE` | `ANTHROPIC_API_KEY` is not set |

Error body format (all 4xx/5xx):

```json
{
  "error": {
    "code": "PACK_NOT_FOUND",
    "message": "Requested pack was not found"
  }
}
```

### Examples

**Default graph:**
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What is quantum entanglement?"}'
```

**Specific pack:**
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "How do channels work?", "pack": "go-expert", "max_results": 5}'
```

**Python:**
```python
import httpx

response = httpx.post(
    "http://localhost:8000/api/v1/chat",
    json={
        "question": "How does garbage collection work in Go?",
        "pack": "go-expert",
        "max_results": 10,
    },
)
response.raise_for_status()
data = response.json()

print(data["answer"])
print("Sources:", data["sources"])
print(f"Answered in {data['execution_time_ms']:.0f}ms via {data['query_type']}")
```

---

## GET /api/v1/chat/stream

Stream a chat response using [Server-Sent Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events) (SSE).

The endpoint opens a persistent HTTP connection and delivers events in this fixed order:

1. **`sources`** — list of article titles used as evidence
2. **`token`** — the complete answer text
3. **`done`** — timing and query metadata
4. **`error`** — emitted instead of `token`/`done` if the agent raises an exception

### Request

```
GET /api/v1/chat/stream?question=<text>&max_results=<n>
Accept: text/event-stream
```

**Query parameters:**

| Parameter | Type | Required | Constraints | Description |
|-----------|------|----------|-------------|-------------|
| `question` | string | Yes | 1–500 chars | Natural language question |
| `max_results` | integer | No | 1–50, default 10 | Maximum vector-search results |

### SSE Events

#### `sources`

Emitted first. Contains the list of article titles the agent used.

```
event: sources
data: ["runtime_scheduling","goroutines","channel_internals"]
```

`data` is a JSON-encoded `string[]`.

#### `token`

The complete synthesized answer as a single plain-text string.

```
event: token
data: Go uses an M:N scheduling model where many goroutines are multiplexed onto a smaller number of OS threads...
```

`data` is a plain string (not JSON-encoded).

#### `done`

Signals that the stream is complete and carries timing metadata.

```
event: done
data: {"query_type": "vector_search", "execution_time_ms": 1240.3}
```

`data` is a JSON object with the same `query_type` and `execution_time_ms` fields
as the blocking `POST /chat` response.

#### `error`

Emitted if the agent raises an unhandled exception. The `done` event is **not** sent.

```
event: error
data: AttributeError
```

`data` is the Python exception class name (e.g. `ValueError`, `RuntimeError`).

### Complete event sequence

```
event: sources
data: ["article_a","article_b"]

event: token
data: The answer text here...

event: done
data: {"query_type": "vector_search", "execution_time_ms": 1240.3}
```

### Error responses

HTTP-level errors (before the stream opens):

| HTTP status | When |
|-------------|------|
| 400 | Query parameter validation failed (e.g. `max_results` out of 1–50 range, or empty `question`) |
| 429 | Rate limit exceeded |
| 503 | `ANTHROPIC_API_KEY` is not set |

Errors that occur after the stream opens (agent or DB errors) are delivered
as `error` events rather than HTTP status codes.

### Examples

**curl:**
```bash
curl -N "http://localhost:8000/api/v1/chat/stream?question=What+is+goroutine+scheduling%3F"
```

**JavaScript (browser EventSource):**
```javascript
const url = new URL('http://localhost:8000/api/v1/chat/stream');
url.searchParams.set('question', 'What is goroutine scheduling?');
url.searchParams.set('max_results', '5');

const es = new EventSource(url);

es.addEventListener('sources', e => {
  const sources = JSON.parse(e.data);
  renderSources(sources);
});

es.addEventListener('token', e => {
  renderAnswer(e.data);
});

es.addEventListener('done', e => {
  const { query_type, execution_time_ms } = JSON.parse(e.data);
  renderMeta(query_type, execution_time_ms);
  es.close();
});

es.addEventListener('error', e => {
  showError(e.data ?? 'Stream error');
  es.close();
});
```

**Python (requests + sseclient):**
```python
import json
import requests
import sseclient

url = 'http://localhost:8000/api/v1/chat/stream'
params = {'question': 'What is goroutine scheduling?', 'max_results': 5}

response = requests.get(url, params=params, stream=True)
response.raise_for_status()

for event in sseclient.SSEClient(response).events():
    if event.event == 'sources':
        print('Sources:', json.loads(event.data))
    elif event.event == 'token':
        print('Answer:', event.data)
    elif event.event == 'done':
        meta = json.loads(event.data)
        print(f"Done ({meta['query_type']}, {meta['execution_time_ms']:.0f}ms)")
        break
    elif event.event == 'error':
        print('Agent error:', event.data)
        break
```

---

## Choosing between POST and GET/stream

| Consideration | POST /chat | GET /chat/stream |
|--------------|------------|-----------------|
| Response format | Single JSON object | Server-Sent Events |
| Latency to first byte | Full round-trip | Faster — sources arrive before answer |
| Browser compatibility | `fetch` + `await` | Native `EventSource` API |
| Pack selection | `pack` field in body | Not supported (uses default graph only) |
| Suitable for | CLI tools, server-to-server calls | Browser chat UIs |

---

## Configuration

The chat endpoints read the following environment variables at startup:

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key — both endpoints return 503 if absent |
| `WIKIGR_DATABASE_PATH` | No | Override the default Kuzu database path |
| `WIKIGR_CHAT_RATE_LIMIT` | No | Override the per-IP rate limit (default `5/minute`) |

Pack databases are resolved at `data/packs/<pack_name>/pack.db` relative to the
server's working directory. Set `WIKIGR_DATABASE_PATH` to an absolute path to
prevent pack lookups from depending on the server's current working directory.

---

## Security notes

- **Pack name validation**: The `pack` field is validated against
  `^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$` before any filesystem access.
  Requests with names that do not match this pattern return `400 INVALID_PACK_NAME`.

- **Empty question (streaming)**: The GET `/chat/stream` endpoint enforces `min_length=1` on
  the `question` parameter (matching the POST endpoint). Empty strings are rejected with HTTP 400
  before reaching the LLM.

- **Rate limiting**: Both endpoints are rate-limited to 5 requests/minute per IP
  via [slowapi](https://pypi.org/project/slowapi/). When deployed behind a reverse
  proxy, configure `forwarded_allow_ips` to match the proxy's CIDR so that the
  real client IP is used rather than the proxy IP.

- **Authentication**: There is no authentication on these endpoints. All callers
  with network access can invoke the Anthropic API. Deploy behind an API gateway
  or add bearer-token middleware for untrusted networks.

- **SSE timeout**: The streaming endpoint enforces a per-connection timeout (default 60 s,
  overridable via `WIKIGR_STREAM_TIMEOUT_S`). When the agent does not respond within the
  timeout an `error` event is emitted and the stream is closed, releasing the database
  connection. For additional protection, front the service with a timeout-aware proxy in
  production.
