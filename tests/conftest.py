import importlib.util
import json
import os
import sys
import unittest.mock
from unittest.mock import MagicMock

# Test doubles for Lambda environment variables.
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")
os.environ.setdefault("BUCKET", "test-bucket")
os.environ.setdefault("TABLE", "test-jobs")
os.environ.setdefault("SITES_TABLE", "test-sites")
os.environ.setdefault("PINECONE_INDEX", "test-index")

# ECS / Fargate environment variables used by fargate.py and task entry points.
os.environ.setdefault("ECS_CLUSTER", "test-cluster")
os.environ.setdefault("IMPLEMENTER_JOB_ID", "test-implement-job")
os.environ.setdefault("IMPLEMENTER_SOURCE_JOB_ID", "test-source-job")
os.environ.setdefault("IMPLEMENTER_REPO", "owner/repo")
os.environ.setdefault("IMPLEMENTER_BASE_BRANCH", "main")
os.environ.setdefault(
    "ECS_TASK_DEFINITION",
    "arn:aws:ecs:us-east-1:000000000000:task-definition/test-agent:1",
)
os.environ.setdefault("ECS_SUBNET_IDS", "subnet-test1,subnet-test2")
os.environ.setdefault("ECS_SECURITY_GROUP", "sg-test")
os.environ.setdefault(
    "RECRAWL_QUEUE_URL",
    "https://sqs.us-east-1.amazonaws.com/000000000000/test-recrawl",
)

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

# Stub service modules that don't exist in this environment so hooks.py can be imported.
for _mod in ("src.services.embeddings", "src.services.logger", "src.services.storage"):
    if importlib.util.find_spec(_mod) is None:
        sys.modules[_mod] = MagicMock()
