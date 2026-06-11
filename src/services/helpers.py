import json
import os
import urllib.request

import boto3

from src.constants import (
    AWS_REGION,
    LAMBDA_EXTENSION_TIMEOUT_SECONDS,
    LAMBDA_EXTENSION_TOKEN_HEADER,
    LAMBDA_EXTENSION_URL,
)
from src.models import SiteMetadata

_secrets_client = boto3.client("secretsmanager", region_name=AWS_REGION)


def build_search_text(metadata: SiteMetadata) -> str:
    """Natural-language description of a site for embedding — what it is, who it's for, and how it feels."""
    parts = [
        metadata.summary,
        metadata.sentiment,
        f"{metadata.industry} · {metadata.site_category} · for {metadata.target_audience}"
        f" · {metadata.business_model} · {metadata.content_tone} tone",
    ]
    if metadata.primary_topics:
        parts.append("Topics: " + ", ".join(metadata.primary_topics))
    if metadata.tech_stack:
        parts.append("Tech: " + ", ".join(metadata.tech_stack))
    if metadata.integrations:
        parts.append("Integrations: " + ", ".join(metadata.integrations))
    if metadata.has_public_api:
        parts.append("Has a public API")
    if metadata.languages:
        parts.append("Languages: " + ", ".join(metadata.languages))
    return ". ".join(parts)


def fetch_secret(secret_name: str) -> str:
    """Returns the secret value from the Lambda extension if available, boto3 otherwise."""
    try:
        url = f"{LAMBDA_EXTENSION_URL}/secretsmanager/get?secretId={secret_name}"
        req = urllib.request.Request(
            url,
            headers={LAMBDA_EXTENSION_TOKEN_HEADER: os.environ["AWS_SESSION_TOKEN"]},
        )
        with urllib.request.urlopen(req, timeout=LAMBDA_EXTENSION_TIMEOUT_SECONDS) as resp:
            return json.loads(json.loads(resp.read())["SecretString"])["value"]
    except Exception:
        response = _secrets_client.get_secret_value(SecretId=secret_name)
        return json.loads(response["SecretString"])["value"]
