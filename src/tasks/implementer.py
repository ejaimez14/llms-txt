import os

from src.agents.implementer import run_implementer


def main() -> None:
    """Fargate task entry point — reads all parameters from environment variables."""
    run_implementer(
        job_id=os.environ["IMPLEMENTER_JOB_ID"],
        source_job_id=os.environ["IMPLEMENTER_SOURCE_JOB_ID"],
        repo=os.environ["IMPLEMENTER_REPO"],
        base_branch=os.environ["IMPLEMENTER_BASE_BRANCH"],
    )


if __name__ == "__main__":
    main()
