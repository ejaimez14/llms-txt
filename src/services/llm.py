import os

import instructor
from agents import Agent, Runner, WebSearchTool, set_default_openai_client
from anthropic import Anthropic
from openai import AsyncOpenAI

from src.constants import (
    ANTHROPIC_SECRET_NAME,
    CLAUDE_AGENT_MODELS,
    CLAUDE_EXTRA_TOOLS,
    CLAUDE_MAX_OUTPUT_TOKENS,
    OPENAI_AGENT_MODELS,
    OPENAI_SECRET_NAME,
    AgentType,
)
from src.models import CompareOutput, CrawlOutput, ReportOutput, UIPlanOutput
from src.services.helpers import fetch_secret
from src.services.hooks import JobHooks
from src.services.tools import web_fetch_tool

_AGENT_OUTPUT_MODEL = {
    AgentType.CRAWL: CrawlOutput,
    AgentType.UI_PLAN: UIPlanOutput,
    AgentType.REPORT: ReportOutput,
    AgentType.COMPARE: CompareOutput,
}


def create_agent(
    model: str,
    agent_type: AgentType,
    job_id: str,
    url: str,
    system_prompt: str,
    max_turns: int = 30,
    timeout_seconds: int = 300,
) -> dict:
    """Returns an agent context dict with hooks pre-attached, ready for run_agent()."""
    if model == "claude":
        return _create_claude_agent(system_prompt, job_id, agent_type, url, model, timeout_seconds)
    elif model == "openai":
        return _create_openai_agent(system_prompt, job_id, agent_type, url, model, max_turns)
    else:
        raise ValueError(f"Unknown model: {model!r}. Supported: 'claude', 'openai'")


def run_agent(agent_ctx: dict, user_content: str) -> dict:
    """Runs the agent and returns the structured output as a dict."""
    if agent_ctx["provider"] == "claude":
        return _run_claude(agent_ctx, user_content)
    if agent_ctx["provider"] == "openai":
        return _run_openai(agent_ctx, user_content)
    raise ValueError(f"Unknown provider: {agent_ctx['provider']}")


# --- Internal ---


def _create_claude_agent(
    system_prompt: str,
    job_id: str,
    agent_type: AgentType,
    url: str,
    model: str,
    timeout_seconds: int = 300,
) -> dict:
    """Builds a Claude instructor context dict with hooks pre-attached."""
    model_id = CLAUDE_AGENT_MODELS.get(agent_type)
    if not model_id:
        raise ValueError(f"No Claude model configured for agent_type={agent_type!r}")
    response_model = _AGENT_OUTPUT_MODEL.get(agent_type)
    if not response_model:
        raise ValueError(f"No response model configured for agent_type={agent_type!r}")
    hooks = JobHooks(job_id, agent_type, url, model)
    return {
        "provider": "claude",
        "model_id": model_id,
        "system_prompt": system_prompt,
        "hooks": hooks,
        "response_model": response_model,
        "extra_tools": CLAUDE_EXTRA_TOOLS.get(agent_type, []),
        "timeout_seconds": timeout_seconds,
    }


def _create_openai_agent(
    system_prompt: str,
    job_id: str,
    agent_type: AgentType,
    url: str,
    model: str,
    max_turns: int = 30,
) -> dict:
    """Builds an OpenAI Agents SDK context dict with hooks pre-attached."""
    model_id = OPENAI_AGENT_MODELS.get(agent_type)
    if not model_id:
        raise ValueError(f"No OpenAI model configured for agent_type={agent_type!r}")
    web_tools = (
        [WebSearchTool(), web_fetch_tool]
        if agent_type in (AgentType.CRAWL, AgentType.UI_PLAN)
        else []
    )
    agent = Agent(
        name=agent_type,
        model=model_id,
        instructions=system_prompt,
        tools=web_tools,
        output_type=_AGENT_OUTPUT_MODEL[agent_type],
    )
    hooks = JobHooks(job_id, agent_type, url, model)
    return {"provider": "openai", "agent": agent, "hooks": hooks, "max_turns": max_turns}


def _run_claude(agent_ctx: dict, user_content: str) -> dict:
    """Uses instructor to call the Anthropic API and return a validated structured output dict."""
    hooks = agent_ctx["hooks"]
    hooks.on_start()
    try:
        kwargs = {
            "model": agent_ctx["model_id"],
            "max_tokens": CLAUDE_MAX_OUTPUT_TOKENS,
            "system": agent_ctx["system_prompt"],
            "messages": [{"role": "user", "content": user_content}],
            "response_model": agent_ctx["response_model"],
        }
        if agent_ctx["extra_tools"]:
            kwargs["tools"] = agent_ctx["extra_tools"]
        output, completion = _instructor_client.messages.create_with_completion(
            **kwargs,
            timeout=agent_ctx["timeout_seconds"],
        )
        output_dict = output.model_dump()
        hooks.on_complete(output_dict, completion.usage)
        return output_dict
    except Exception as exc:
        hooks.on_error(exc)
        raise


def _run_openai(agent_ctx: dict, user_content: str) -> dict:
    """Runs the OpenAI agent via Runner; returns the structured output as a dict."""
    hooks = agent_ctx["hooks"]
    hooks.on_start()
    try:
        result = Runner.run_sync(agent_ctx["agent"], user_content, max_turns=agent_ctx["max_turns"])
        raw_output = result.final_output.model_dump()
        hooks.on_complete(raw_output, result.context_wrapper.usage)
        return raw_output
    except Exception as exc:
        hooks.on_error(exc)
        raise


# In Lambda the extension serves secrets from localhost:2773.
# Locally that port doesn't exist, so fall back to env vars for development.
_anthropic_client = Anthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY") or fetch_secret(ANTHROPIC_SECRET_NAME)
)
_instructor_client = instructor.from_anthropic(_anthropic_client)
_openai_client = AsyncOpenAI(
    api_key=os.environ.get("OPENAI_API_KEY") or fetch_secret(OPENAI_SECRET_NAME)
)
set_default_openai_client(_openai_client)
