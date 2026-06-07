# Component: Search Service

## How to Use This Plan

You are implementing **Component 13: Search Service**. Your job is to produce `src/services/search.py`. This is not an agent — it is a synchronous service function with no job ID, no hooks, and no LLM call. It embeds a query string and finds semantically similar crawled content in Pinecone.

Dependencies:
- [04-models-constants-prompts.md](04-models-constants-prompts.md) — `SearchResponse` and `SearchResult` from `src/models.py`
- [05-embeddings-service.md](05-embeddings-service.md) — `embed_text` must be available
- [06-pinecone-service.md](06-pinecone-service.md) — `query_vectors` must be available
- [03-storage-service.md](03-storage-service.md) — `generate_download_url` must be available

Related plans:
- [02-lambda-handler.md](02-lambda-handler.md) — handler calls `run_search` directly and serializes `SearchResponse` to JSON; import from `src.services.search`, not `src.agents.search`

---

## Owner

Backend subagent

## Output Files

```
src/
  services/
    search.py
tests/
  test_search.py
```

---

## Entry Point

```python
def run_search(query: str) -> SearchResponse:
    """
    Embeds the query, searches Pinecone for similar content,
    and returns ranked results with presigned download URLs.
    On Pinecone error, returns an empty result set with the error field set.
    """
```

---

## Behavior

1. If `query` is empty, return `SearchResponse(query=query, results=[])` immediately.
2. Embed the query via `embed_text(query)`.
3. Query Pinecone via `query_vectors(vector, top_k=10)`.
4. For each match, call `generate_download_url(s3_key)` to produce a presigned URL.
5. Return a `SearchResponse` with results ranked by descending score.
6. If any exception is raised during embedding or querying, return `SearchResponse(query=query, results=[], error="Search unavailable")` — do not raise.

---

## Implementation

```python
from src.models import ModelName, SearchResponse, SearchResult
from src.services.embeddings import embed_text
from src.services.pinecone_client import query_vectors
from src.services.storage import generate_download_url


def run_search(query: str) -> SearchResponse:
    """
    Embeds the query, searches Pinecone for similar content,
    and returns ranked results with presigned download URLs.
    On Pinecone error, returns an empty result set with the error field set.
    """
    if not query:
        return SearchResponse(query=query, results=[])

    try:
        vector = embed_text(query)
        matches = query_vectors(vector, top_k=10)
    except Exception:
        return SearchResponse(query=query, results=[], error="Search unavailable")

    results = [
        SearchResult(
            jobId=match["id"],
            score=match["score"],
            url=match["metadata"]["url"],
            s3Key=match["metadata"]["s3Key"],
            model=ModelName(match["metadata"].get("model", ModelName.CLAUDE)),
            downloadUrl=generate_download_url(match["metadata"]["s3Key"]),
        )
        for match in matches
    ]
    return SearchResponse(query=query, results=results)
```

---

## Acceptance Criteria

- Results are ranked by similarity score (highest first — Pinecone returns them in order, preserve it)
- Each result includes a presigned download URL
- Each result includes the `model` field populated from Pinecone metadata
- Empty query returns immediately with no Pinecone call
- Pinecone errors return `SearchResponse` with `error="Search unavailable"` — function never raises

---

## Tests

**File:** `tests/test_search.py`
Use `pytest`. Mock `embed_text`, `query_vectors`, and `generate_download_url` with `pytest-mock`.

| Test | Type | Verifies |
|------|------|----------|
| `test_search_returns_ranked_results` | happy | results match Pinecone order, each has a presigned URL |
| `test_search_empty_query_returns_empty` | happy | returns `SearchResponse` with no results and no Pinecone call |
| `test_search_pinecone_error_returns_error_field` | unhappy | returns `SearchResponse(results=[], error="Search unavailable")` on exception |
