import os

from pinecone import Pinecone

from src.constants import PINECONE_SECRET_NAME
from src.services.logger import get_logger
from src.services.helpers import fetch_secret

logger = get_logger(__name__)


# --- Upsert Operations ---


def upsert_vector(job_id: str, vector: list[float], metadata: dict) -> None:
    """Upserts a single vector into Pinecone using job_id as the vector ID."""
    # Pinecone rejects null metadata values, so drop keys whose value is None.
    clean_metadata = {key: value for key, value in metadata.items() if value is not None}
    try:
        _index.upsert(
            vectors=[{"id": job_id, "values": vector, "metadata": clean_metadata}]
        )
    except Exception as exc:
        logger.error({"event": "pinecone_upsert_failed", "error": str(exc)})
        raise


# --- Query Operations ---


def query_vectors(vector: list[float], top_k: int = 10) -> list[dict]:
    """Queries Pinecone by vector similarity and returns top_k matches."""
    try:
        response = _index.query(vector=vector, top_k=top_k, include_metadata=True)
    except Exception as exc:
        logger.error({"event": "pinecone_query_failed", "error": str(exc)})
        raise

    return [
        {
            "id": match["id"],
            "score": match["score"],
            "metadata": match.get("metadata", {}),
        }
        for match in response["matches"]
    ]


# In Lambda the extension serves secrets from localhost:2773.
# Locally that port doesn't exist, so fall back to env vars for development.
_client = Pinecone(
    api_key=os.environ.get("PINECONE_API_KEY") or fetch_secret(PINECONE_SECRET_NAME)
)
_index = _client.Index(os.environ["PINECONE_INDEX"])
