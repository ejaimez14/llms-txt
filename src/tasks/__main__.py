import os

from src.constants import AgentType
from src.tasks.base import REGISTRY, run_task

run_task(
    job_id=os.environ["AGENT_ID"],
    url=os.environ["AGENT_URL"],
    model=os.environ["AGENT_MODEL"],
    config=REGISTRY.get(AgentType(os.environ["AGENT_TYPE"])),
)
