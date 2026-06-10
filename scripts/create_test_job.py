"""Creates a minimal job record in DynamoDB for local task testing.

Prints the generated job ID to stdout so it can be captured by the Makefile.

Usage: uv run python scripts/create_test_job.py <url> <model>
"""
import sys
import uuid

from src.services.storage import create_job

url = sys.argv[1]
model = sys.argv[2]
job_id = str(uuid.uuid4())
create_job(job_id, url, model)
print(job_id, end="")
