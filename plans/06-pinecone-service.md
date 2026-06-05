# Component: Pinecone Service

## How to Use This Plan

You are implementing **Component 6: Pinecone Service**. Your job is to produce `src/services/pinecone_client.py`. This is a thin wrapper — keep it simple.

Dependencies: [04-models-constants-prompts.md](04-models-constants-prompts.md) — use `ModelName` enum when storing model in metadata.

Related plans:
- [07-agent-factory-hooks.md](07-agent-factory-hooks.md) — the crawl completion hook calls `upsert_vector`
- [13-search-endpoint.md](13-search-endpoint.md) — calls `query_vectors` to find similar content
- [05-embeddings-service.md](05-embeddings-service.md) — produces the vectors passed into this service

---

## Owner

Backend subagent

## Output Files

```
src/
  services/
    pinecone_client.py
```

---

## Functions

```python
def upsert_vector(job_id: str, vector: list[float], metadata: dict) -> None:
    """
    Upserts a single vector into Pinecone.
    Uses job_id as the vector ID.
    Metadata must always include 'url' and 's3Key'.
    """

def query_vectors(vector: list[float], top_k: int = 10) -> list[dict]:
    """
    Queries Pinecone by vector similarity.
    Returns top_k matches as a list of dicts, each with:
    - id (job_id)
    - score (similarity score)
    - metadata (url, s3Key, model, etc.)
    Returns an empty list on Pinecone connection errors.
    """
```

---

## Environment Variables

- `PINECONE_API_KEY`
- `PINECONE_INDEX`

---

## Metadata Contract

Every upserted vector must include at minimum:

```python
from src.constants import ModelName

{
    "url": "https://example.com",
    "s3Key": "results/abc123/llms.txt",
    "model": ModelName.CLAUDE.value   # store as string value for Pinecone compatibility
}
```

The `query_vectors` return structure maps directly to `SearchResult` in `src/models.py` — the search endpoint assembles the final `SearchResponse` from these dicts.

---

## Acceptance Criteria

- Metadata always includes `url` and `s3Key`
- Query results include similarity scores
- Handles Pinecone connection errors gracefully (return empty list, log the error)

---

## Tests

**File:** `tests/test_pinecone_client.py`
Use `pytest`. Mock AWS with `moto[s3,dynamodb]`. Mock Bedrock and external APIs with `pytest-mock`.

| Test | Type | Verifies |
|------|------|----------|
| `test_upsert_vector_succeeds` | happy | upserts vector with `url` and `s3Key` metadata fields |
| `test_query_vectors_returns_ranked_results` | happy | returns list of dicts with `id`, `score`, and `metadata` |
| `test_query_vectors_connection_error_returns_empty` | unhappy | returns `[]` when Pinecone raises a connection error |
