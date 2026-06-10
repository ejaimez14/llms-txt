import importlib.util
import json
import os
import sys
import unittest.mock
from unittest.mock import MagicMock

# AWS credentials: setdefault so existing creds aren't clobbered when running locally.
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")

# All other env vars are forced to test values so real .env exports never leak
# into test assertions (the Makefile's `export` directive passes .env to pytest).
os.environ["BUCKET"] = "test-bucket"
os.environ["TABLE"] = "test-jobs"
os.environ["SITES_TABLE"] = "test-sites"
os.environ["PINECONE_INDEX"] = "test-index"
os.environ["ECS_CLUSTER"] = "test-cluster"
os.environ["ECS_TASK_DEFINITION"] = (
    "arn:aws:ecs:us-east-1:000000000000:task-definition/test-agent:1"
)
os.environ["ECS_SUBNET_IDS"] = "subnet-test1,subnet-test2"
os.environ["ECS_SECURITY_GROUP"] = "sg-test"
os.environ["RECRAWL_QUEUE_URL"] = (
    "https://sqs.us-east-1.amazonaws.com/000000000000/test-recrawl"
)
os.environ["AGENT_ID"] = "test-agent-id-00000000"
os.environ.setdefault("IMPLEMENTER_SOURCE_JOB_ID", "test-source-job")
# llm.py and pinecone_client.py call fetch_secret() at import time via the Lambda extension.
# The extension isn't running in tests — intercept the HTTP call before any module is imported.
_secret_body = json.dumps({"SecretString": json.dumps({"value": "test-key"})}).encode()
_mock_http = MagicMock(read=MagicMock(return_value=_secret_body))
_mock_http.__enter__ = lambda s: s
_mock_http.__exit__ = MagicMock(return_value=False)
unittest.mock.patch("urllib.request.urlopen", return_value=_mock_http).start()

# pinecone is installed as the legacy pinecone-client package which raises on import.
sys.modules.setdefault("pinecone", MagicMock())

# claude_agent_sdk is not installed in the test environment — stub it.
sys.modules.setdefault("claude_agent_sdk", MagicMock())
sys.modules.setdefault("claude_agent_sdk.types", MagicMock())

# Stub service modules that don't exist in this environment so hooks.py can be imported.
for _mod in ("src.services.embeddings", "src.services.logger", "src.services.storage"):
    if importlib.util.find_spec(_mod) is None:
        sys.modules[_mod] = MagicMock()
