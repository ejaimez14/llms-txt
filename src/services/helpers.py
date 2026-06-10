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

_secrets_client = boto3.client("secretsmanager", region_name=AWS_REGION)


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
