import logging
import os

from pinecone import Pinecone

logger = logging.getLogger(__name__)

_client = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
_index = _client.Index(os.environ["PINECONE_INDEX"])


# --- Upsert Operations ---


def upsert_vector(job_id: str, vector: list[float], metadata: dict) -> None:
    """Upserts a single vector into Pinecone using job_id as the vector ID.

    Metadata must always include 'url' and 's3Key'.
    """
    _index.upsert(vectors=[{"id": job_id, "values": vector, "metadata": metadata}])


# --- Query Operations ---


def query_vectors(vector: list[float], top_k: int = 10) -> list[dict]:
    """Queries Pinecone by vector similarity.

    Returns top_k matches as a list of dicts with 'id', 'score', and 'metadata'.
    Returns an empty list on Pinecone connection errors.
    """
    try:
        response = _index.query(vector=vector, top_k=top_k, include_metadata=True)
    except Exception as exc:
        logger.error("Pinecone query failed: %s", exc)
        return []

    return [
        {
            "id": match["id"],
            "score": match["score"],
            "metadata": match.get("metadata", {}),
        }
        for match in response["matches"]
    ]
