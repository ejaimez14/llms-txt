import os

from src.agents.implementer import run_implementer
from src.constants import AgentType
from src.tasks.base import run_task
from src.tasks.registry import REGISTRY

_agent_type = AgentType(os.environ["AGENT_TYPE"])

if _agent_type == AgentType.IMPLEMENT:
    run_implementer(
        job_id=os.environ["AGENT_ID"],
        source_job_id=os.environ["IMPLEMENTER_SOURCE_JOB_ID"],
        repo=os.environ["IMPLEMENTER_REPO"],
        base_branch=os.environ["IMPLEMENTER_BASE_BRANCH"],
    )
else:
    run_task(
        job_id=os.environ["AGENT_ID"],
        url=os.environ["AGENT_URL"],
        model=os.environ["AGENT_MODEL"],
        config=REGISTRY.get(_agent_type),
    )
