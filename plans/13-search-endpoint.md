# Component: Search Endpoint

## How to Use This Plan

You are implementing **Component 13: Search Endpoint**. Your job is to produce `src/agents/search.py`. This is the only synchronous endpoint in the system — no job pattern needed. It embeds a query and finds semantically similar crawled content.

Dependencies: [04-models-constants-prompts.md](04-models-constants-prompts.md) — return type is `SearchResponse` from `src/models.py`. [05-embeddings-service.md](05-embeddings-service.md) and [06-pinecone-service.md](06-pinecone-service.md) must be available (or stubbed).

Related plans:
- [05-embeddings-service.md](05-embeddings-service.md) — `embed_text` is called here
- [06-pinecone-service.md](06-pinecone-service.md) — `query_vectors` is called here
- [03-storage-service.md](03-storage-service.md) — `generate_download_url` is called here
- [02-lambda-handler.md](02-lambda-handler.md) — handler calls `run_search` directly

---

## Owner

Backend subagent

## Output Files

```
src/
  agents/
    search.py
```

---

## Entry Point

```python
from src.models import SearchResponse

def run_search(query: str) -> SearchResponse:
    """
    Embeds the query, searches Pinecone for similar content,
    and returns ranked results with download URLs.
    Returns SearchResponse — the handler serializes this to JSON directly.
    """
```

---

## Behavior

1. Take the query string
2. Embed it via `embed_text(query)` (Bedrock Titan)
3. Query Pinecone via `query_vectors(vector, top_k=10)`
4. For each match, generate a presigned S3 download URL via `generate_download_url(s3_key)`
5. Return results ranked by similarity score

---

## Response Format

Returns a `SearchResponse` (defined in `src/models.py`). Shape:

```json
{
  "query": "what sites have pricing pages",
  "results": [
    {
      "jobId": "abc123",
      "url": "https://example.com",
      "model": "claude",
      "score": 0.91,
      "s3Key": "results/abc123/llms.txt",
      "downloadUrl": "https://s3.presigned.url/..."
    }
  ],
  "error": null
}
```

The `model` field shows which LLM produced each crawl result. On Pinecone error, `results` is `[]` and `error` is set.

---

## Edge Cases

- Empty query string: return `{"query": "", "results": []}`
- No Pinecone results: return `{"query": "...", "results": []}`
- Pinecone connection error: return `{"query": "...", "results": [], "error": "Search unavailable"}`

---

## Acceptance Criteria

- Results are ranked by similarity score (highest first)
- Each result includes a presigned download URL
- Each result includes the `model` field
- Handles empty queries and no-results gracefully
- Handles Pinecone connection errors without crashing

---

## Tests

**File:** `tests/test_search.py`
Use `pytest`. Mock AWS with `moto[s3,dynamodb]`. Mock Bedrock and external APIs with `pytest-mock`.

| Test | Type | Verifies |
|------|------|----------|
| `test_search_returns_ranked_results` | happy | results sorted by descending score with presigned S3 URL on each |
| `test_search_pinecone_error_returns_error_field` | unhappy | returns `{"results": [], "error": "..."}` on Pinecone failure |
