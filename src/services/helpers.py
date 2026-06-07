import json
import os
import urllib.request


def fetch_secret(secret_name: str) -> str:
    """Fetches a secret value from the Lambda Parameters and Secrets Extension (localhost cache)."""
    url = f"http://localhost:2773/secretsmanager/get?secretId={secret_name}"
    req = urllib.request.Request(
        url, headers={"X-Aws-Parameters-Secrets-Token": os.environ["AWS_SESSION_TOKEN"]}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(json.loads(resp.read())["SecretString"])["value"]
