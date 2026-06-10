import json

import boto3
from botocore.exceptions import ClientError

from src.constants import AWS_REGION, TITAN_EMBED_DIMENSIONS, TITAN_EMBED_MODEL, TITAN_MAX_INPUT_CHARS
from src.services.logger import get_logger

logger = get_logger(__name__)

_bedrock_client = boto3.client("bedrock-runtime", region_name=AWS_REGION)


def embed_text(text: str | None) -> list[float]:
    """Embeds text using Amazon Bedrock Titan Embed Text v2.

    Truncates input to TITAN_MAX_INPUT_CHARS before embedding.
    Returns an empty list if text is empty or None.
    """
    if not text:
        return []

    truncated = text[:TITAN_MAX_INPUT_CHARS]

    try:
        response = _bedrock_client.invoke_model(
            modelId=TITAN_EMBED_MODEL,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(
                {
                    "inputText": truncated,
                    "dimensions": TITAN_EMBED_DIMENSIONS,
                    "normalize": True,
                }
            ),
        )
        response_body = json.loads(response["body"].read())
    except ClientError as exc:
        logger.error({"event": "bedrock_embed_failed", "error": str(exc)})
        raise

    return response_body["embedding"]
