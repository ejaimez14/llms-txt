import os
import sys
from unittest.mock import MagicMock

os.environ.setdefault("PINECONE_API_KEY", "test-key")
os.environ.setdefault("PINECONE_INDEX", "test-index")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("BUCKET", "test-bucket")
os.environ.setdefault("TABLE", "test-jobs")
os.environ.setdefault("SITES_TABLE", "test-sites")
sys.modules.setdefault("pinecone", MagicMock())
