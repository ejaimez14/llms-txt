from anthropic import Anthropic
from agents import Agent, Runner, WebSearchTool, set_default_openai_client
from openai import AsyncOpenAI

from src.constants import (
    ANTHROPIC_SECRET_NAME,
    CLAUDE_AGENT_MODELS,
    CLAUDE_MAX_OUTPUT_TOKENS,
    OPENAI_AGENT_MODELS,
    OPENAI_SECRET_NAME,
)
from src.models import CompareOutput, CrawlOutput, ReportOutput, UIPlanOutput
from src.services.helpers import fetch_secret
from src.services.hooks import JobHooks
from src.services.tools import web_fetch_tool

_OPENAI_OUTPUT_TYPE = {
    "crawl": CrawlOutput,
    "ui-plan": UIPlanOutput,
    "report": ReportOutput,
    "compare": CompareOutput,
}


def create_agent(
    model: str,
    agent_type: str,
    job_id: str,
    url: str,
    system_prompt: str,
    tools: list | None = None,
    submit_tool_name: str | None = None,
) -> dict:
    """Returns an agent context dict with hooks pre-attached, ready for run_agent()."""
    if model == "claude":
        return _create_claude_agent(
            system_prompt, job_id, agent_type, url, model, tools, submit_tool_name
        )
    elif model == "openai":
        return _create_openai_agent(system_prompt, job_id, agent_type, url, model)
    else:
        raise ValueError(f"Unknown model: {model!r}. Supported: 'claude', 'openai'")


def run_agent(agent_ctx: dict, user_content: str) -> dict | str:
    """Runs the agent and returns the submit tool's structured output, or plain text if no submit tool is set."""
    if agent_ctx["provider"] == "claude":
        return _run_claude(agent_ctx, user_content)
    if agent_ctx["provider"] == "openai":
        return _run_openai(agent_ctx, user_content)
    raise ValueError(f"Unknown provider: {agent_ctx['provider']}")


# --- Internal ---


def _create_claude_agent(
    system_prompt: str,
    job_id: str,
    agent_type: str,
    url: str,
    model: str,
    tools: list | None = None,
    submit_tool_name: str | None = None,
) -> dict:
    model_id = CLAUDE_AGENT_MODELS.get(agent_type)
    if not model_id:
        raise ValueError(f"No Claude model configured for agent_type={agent_type!r}")
    hooks = JobHooks(job_id, agent_type, url, model)
    return {
        "provider": "claude",
        "model_id": model_id,
        "client": _anthropic_client,
        "system_prompt": system_prompt,
        "hooks": hooks,
        "tools": tools or [],
        "submit_tool_name": submit_tool_name,
    }


def _create_openai_agent(
    system_prompt: str,
    job_id: str,
    agent_type: str,
    url: str,
    model: str,
) -> dict:
    """Builds an OpenAI Agents SDK context dict with hooks pre-attached."""
    model_id = OPENAI_AGENT_MODELS.get(agent_type)
    if not model_id:
        raise ValueError(f"No OpenAI model configured for agent_type={agent_type!r}")
    # Crawl and UI plan need live web access; report and compare receive content as text.
    web_tools = (
        [WebSearchTool(), web_fetch_tool] if agent_type in ("crawl", "ui-plan") else []
    )
    agent = Agent(
        name=agent_type,
        model=model_id,
        instructions=system_prompt,
        tools=web_tools,
        output_type=_OPENAI_OUTPUT_TYPE[agent_type],
    )
    hooks = JobHooks(job_id, agent_type, url, model)
    return {"provider": "openai", "agent": agent, "hooks": hooks}


def _run_claude(agent_ctx: dict, user_content: str) -> dict | str:
    """Makes one Anthropic API call; returns the submit tool's input dict, or plain text on end_turn."""
    client = agent_ctx["client"]
    hooks = agent_ctx["hooks"]
    submit_tool_name = agent_ctx.get("submit_tool_name")
    hooks.on_start()

    messages = [{"role": "user", "content": user_content}]

    try:
        response = client.messages.create(
            model=agent_ctx["model_id"],
            max_tokens=CLAUDE_MAX_OUTPUT_TOKENS,
            system=agent_ctx["system_prompt"],
            tools=agent_ctx["tools"],
            messages=messages,
        )

        if response.stop_reason == "tool_use" and submit_tool_name:
            for block in response.content:
                if block.type == "tool_use" and block.name == submit_tool_name:
                    hooks.on_complete(block.input, response.usage)
                    return block.input
            raise ValueError(
                f"Expected submit tool call '{submit_tool_name}' not found in response"
            )

        # Reached only when submit_tool_name is None — caller receives plain text directly.
        output = next(b.text for b in response.content if hasattr(b, "text"))
        hooks.on_complete(output, response.usage)
        return output

    except Exception as exc:
        hooks.on_error(exc)
        raise


def _run_openai(agent_ctx: dict, user_content: str) -> dict:
    """Runs the OpenAI agent via Runner; returns the structured output as a dict."""
    hooks = agent_ctx["hooks"]
    hooks.on_start()
    try:
        result = Runner.run_sync(agent_ctx["agent"], user_content)
        raw_output = result.final_output.model_dump()
        hooks.on_complete(raw_output, result.context_wrapper.usage)
        return raw_output
    except Exception as exc:
        hooks.on_error(exc)
        raise


_anthropic_client = Anthropic(api_key=fetch_secret(ANTHROPIC_SECRET_NAME))
_openai_client = AsyncOpenAI(api_key=fetch_secret(OPENAI_SECRET_NAME))
set_default_openai_client(_openai_client)
