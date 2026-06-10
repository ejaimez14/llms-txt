"""Agent troubleshooting helper: seeds a DynamoDB job record for use with make local-task."""
import sys
import uuid

from src.services.storage import create_job

def main(url: str, model: str) -> None:
    job_id = str(uuid.uuid4())
    create_job(job_id, url, model)
    print(job_id, end="")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
