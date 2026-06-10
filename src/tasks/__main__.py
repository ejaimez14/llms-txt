import os

from src.constants import AgentType
from src.tasks.base import run_task
from src.tasks.registry import REGISTRY


def main() -> None:
    run_task(
        job_id=os.environ["AGENT_ID"],
        url=os.environ["AGENT_URL"],
        model=os.environ["AGENT_MODEL"],
        config=REGISTRY.get(AgentType(os.environ["AGENT_TYPE"])),
    )


if __name__ == "__main__":
    main()
