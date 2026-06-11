from src.constants import SEARCH_TOP_K
from src.models import ModelName, SearchResponse, SearchResult
from src.services.embeddings import embed_text
from src.services.pinecone_client import query_vectors
from src.services.storage import generate_download_url


def run_search(query: str) -> SearchResponse:
    """
    Embeds the query, searches Pinecone for similar content,
    and returns ranked results with presigned download URLs.
    On any exception, returns an empty result set with the error field set.
    """
    if not query:
        return SearchResponse(query=query, results=[])

    try:
        vector = embed_text(query)
        matches = query_vectors(vector, top_k=SEARCH_TOP_K)
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
