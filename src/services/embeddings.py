import json

import boto3
from botocore.exceptions import ClientError

from src.constants import TITAN_EMBED_MODEL
from src.services.logger import get_logger

logger = get_logger(__name__)

_MAX_INPUT_CHARS = 25000

_bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")


def embed_text(text: str | None) -> list[float]:
    """Embeds text using Amazon Bedrock Titan Embed Text v1.

    Truncates input to 25000 characters (~6250 tokens, within Titan's 8192-token limit).
    Returns an empty list if text is empty or None.
    """
    if not text:
        return []

    truncated = text[:_MAX_INPUT_CHARS]

    try:
        response = _bedrock_client.invoke_model(
            modelId=TITAN_EMBED_MODEL,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({"inputText": truncated}),
        )
        response_body = json.loads(response["body"].read())
    except ClientError as exc:
        logger.info({"event": "bedrock_embed_failed", "error": str(exc)})
        raise

    return response_body["embedding"]
