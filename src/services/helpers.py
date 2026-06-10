import json
import os
import urllib.request

import boto3

from src.services.logger import get_logger

logger = get_logger(__name__)

_secrets_client = boto3.client(
    "secretsmanager",
    region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
)


def fetch_secret(secret_name: str) -> str:
    """Fetches a secret value from the Lambda extension if available, boto3 otherwise.

    The Lambda Parameters and Secrets Extension runs on localhost:2773 inside Lambda but not
    in ECS Fargate. The boto3 fallback handles the ECS case (e.g. the implement task, which
    omits ANTHROPIC_API_KEY so llm.py module init falls through to fetch_secret).
    """
    try:
        url = f"http://localhost:2773/secretsmanager/get?secretId={secret_name}"
        req = urllib.request.Request(
            url,
            headers={"X-Aws-Parameters-Secrets-Token": os.environ["AWS_SESSION_TOKEN"]},
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            return json.loads(json.loads(resp.read())["SecretString"])["value"]
    except Exception as exc:
        logger.error({"event": "lambda_extension_unavailable", "error": str(exc)})
        response = _secrets_client.get_secret_value(SecretId=secret_name)
        return json.loads(response["SecretString"])["value"]
