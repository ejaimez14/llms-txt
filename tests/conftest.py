import os
import sys
from unittest.mock import MagicMock

# Env vars and pinecone stub must be in place before pinecone_client is imported at collection time.
os.environ.setdefault("PINECONE_API_KEY", "test-key")
os.environ.setdefault("PINECONE_INDEX", "test-index")
sys.modules.setdefault("pinecone", MagicMock())
