# Component: Embeddings Service

## How to Use This Plan

You are implementing **Component 5: Embeddings Service**. Your job is to produce `src/services/embeddings.py`. This is a thin wrapper — keep it simple.

Dependencies: **None** — testable with a real Bedrock client or a mock.

Related plans:
- [07-agent-factory-hooks.md](07-agent-factory-hooks.md) — the crawl completion hook calls `embed_text`
- [13-search-endpoint.md](13-search-endpoint.md) — search embeds the query before querying Pinecone
- [06-pinecone-service.md](06-pinecone-service.md) — the vector produced here is passed to Pinecone

---

## Owner

Backend subagent

## Output Files

```
src/
  services/
    embeddings.py
```

---

## Functions

```python
def embed_text(text: str) -> list[float]:
    """
    Embeds text using Amazon Bedrock Titan Embed Text v1.
    Truncates input to 8000 characters before embedding (Titan token limit safety).
    Returns a list of floats (the embedding vector).
    Returns an empty list if text is empty or None.
    """
```

---

## Implementation Notes

- Use `boto3` with the `bedrock-runtime` client
- Model ID: `amazon.titan-embed-text-v1`
- Truncate input to 8000 characters — do this before the API call, not after
- Handle empty/null input gracefully (return `[]` rather than raising)

---

## Acceptance Criteria

- Uses `boto3` `bedrock-runtime` client
- Truncates input to 8000 characters
- Handles empty/null text without raising
- Returns a `list[float]`

---

## Tests

**File:** `tests/test_embeddings.py`
Use `pytest`. Mock AWS with `moto[s3,dynamodb]`. Mock Bedrock and external APIs with `pytest-mock`.

| Test | Type | Verifies |
|------|------|----------|
| `test_embed_text_returns_float_list` | happy | returns a non-empty `list[float]` for valid input |
| `test_embed_calls_bedrock_titan` | happy | invokes `bedrock-runtime` with model `amazon.titan-embed-text-v1` |
| `test_embed_truncates_long_input` | edge | input over 8000 characters is truncated before the API call |
| `test_embed_bedrock_error_raises` | unhappy | re-raises the exception when Bedrock call fails |
