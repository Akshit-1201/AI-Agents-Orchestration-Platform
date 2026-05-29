"""Graph node builders.

- Agent node: an LLM + tool-calling loop (Gemini->Ollama fallback) that records tool
  calls AND their results, per-message token/cost, and the attributed assistant message;
  enforces the agent's limits (max_steps/tokens/cost/timeout) and guardrails (output length).
- Supervisor node: an LLM router honoring interaction_rules (allowed_targets / can_delegate).
- Conditional router: LLM-judged routing across a node's conditioned out-edges.
"""
import asyncio
import logging
import re
import time
from typing import Callable, List

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool

from config import price_for, settings
from models import Agent, MessageRole
from runtime.providers import ainvoke_chat
from runtime.state import RunState

logger = logging.getLogger("yuno.runtime.nodes")


def _system_text(agent: Agent) -> str:
    parts = [agent.system_prompt or ""]
    if agent.role:
        parts.append(f"Your role: {agent.role}.")
    blocked = (agent.guardrails or {}).get("blocked_topics") or []
    if blocked:
        parts.append("Refuse to discuss these topics: " + ", ".join(blocked) + ".")
    return "\n".join(p for p in parts if p)


def _max_iters(agent: Agent) -> int:
    return int((agent.limits or {}).get("max_steps") or settings.default_max_steps)


async def _run_tool(tool_map, call) -> str:
    tool = tool_map.get(call["name"])
    if tool is None:
        return f"Error: unknown tool '{call['name']}'"
    try:
        return str(await tool.ainvoke(call["args"]))
    except Exception as e:  # noqa: BLE001
        return f"Error running {call['name']}: {e}"


def _match_choice(text: str, options: List[str]) -> str:
    """Pick the option named in `text`: exact match first, then whole-word match
    (longest option first) so 'n10' is never shadowed by 'n1'."""
    low = (text or "").strip().lower()
    for opt in options:
        if low == opt.lower():
            return opt
    for opt in sorted(options, key=len, reverse=True):
        if re.search(rf"\b{re.escape(opt.lower())}\b", low):
            return opt
    return "FINISH" if "FINISH" in options else (options[0] if options else "FINISH")


def make_agent_node(agent: Agent, node_key: str, tools: List[BaseTool], recorder) -> Callable:
    tool_map = {t.name: t for t in tools}
    max_iters = _max_iters(agent)
    limits = agent.limits or {}
    guardrails = agent.guardrails or {}
    max_tokens = limits.get("max_tokens")
    max_cost = limits.get("max_cost_usd")
    timeout = limits.get("timeout_seconds")
    max_chars = guardrails.get("max_output_chars")
    price_in, price_out = price_for(agent.model)

    async def _execute(state: RunState):
        await recorder.event("step_start", {"node": node_key, "agent": agent.name})
        work = [SystemMessage(content=_system_text(agent))] + list(state.get("messages", []))
        produced, last_ai = [], None
        n_prompt = n_completion = 0
        node_cost = 0.0
        stop_reason = None

        for _ in range(max_iters):
            resp, usage, provider = await ainvoke_chat(work, tools, agent.model)
            await recorder.usage(agent.model, usage)
            n_prompt += usage.get("input", 0)
            n_completion += usage.get("output", 0)
            node_cost = (n_prompt / 1000.0) * price_in + (n_completion / 1000.0) * price_out
            await recorder.event(
                "llm_chunk",
                {"node": node_key, "provider": provider, "content": (resp.content or "")[:500]},
            )
            work.append(resp)
            produced.append(resp)
            last_ai = resp

            if max_tokens and (n_prompt + n_completion) >= max_tokens:
                stop_reason = "max_tokens"
                break
            if max_cost and node_cost >= max_cost:
                stop_reason = "max_cost_usd"
                break

            calls = getattr(resp, "tool_calls", None) or []
            if not calls:
                break
            for call in calls:
                start = time.perf_counter()
                result = await _run_tool(tool_map, call)
                duration_ms = int((time.perf_counter() - start) * 1000)
                status = "error" if result.startswith("Error") else "ok"
                await recorder.event(
                    "tool_call",
                    {"node": node_key, "tool": call["name"], "args": call["args"],
                     "result": result[:1000], "status": status, "duration_ms": duration_ms},
                )
                await recorder.message(
                    role=MessageRole.tool, content=result, agent_id=agent.id,
                    source_node_key=node_key, tool_call_id=call.get("id"),
                )
                work.append(ToolMessage(content=result, tool_call_id=call["id"]))
                produced.append(work[-1])

        if last_ai is not None:
            content = last_ai.content or ""
            if max_chars and len(content) > max_chars:
                content = content[:max_chars]
            await recorder.message(
                role=MessageRole.assistant, content=content, agent_id=agent.id,
                source_node_key=node_key, prompt_tokens=n_prompt,
                completion_tokens=n_completion, cost_usd=round(node_cost, 6),
            )
        await recorder.event(
            "step_end", {"node": node_key, **({"stopped": stop_reason} if stop_reason else {})}
        )
        return {"messages": produced}

    async def node(state: RunState):
        if timeout:
            try:
                return await asyncio.wait_for(_execute(state), timeout=float(timeout))
            except asyncio.TimeoutError:
                await recorder.event("error", {"node": node_key, "error": f"timeout after {timeout}s"})
                return {"messages": []}
        return await _execute(state)

    return node


def make_supervisor_node(agent: Agent, node_key: str, out_keys: List[str], recorder) -> Callable:
    rules = agent.interaction_rules or {}
    allowed = rules.get("allowed_targets") or []
    can_delegate = rules.get("can_delegate", True)
    effective = [k for k in out_keys if (not allowed or k in allowed)]
    if not can_delegate:
        effective = []
    options = effective + ["FINISH"]

    async def node(state: RunState):
        await recorder.event(
            "step_start", {"node": node_key, "agent": agent.name, "role": "supervisor"}
        )
        sys = (
            f"{_system_text(agent)}\n\nYou are a supervisor coordinating workers. "
            f"Based on the conversation so far, decide who should act next. "
            f"Reply with EXACTLY one of: {', '.join(options)}."
        )
        msgs = [SystemMessage(content=sys)] + list(state.get("messages", []))
        resp, usage, provider = await ainvoke_chat(msgs, None, agent.model)
        await recorder.usage(agent.model, usage)
        choice = _match_choice(resp.content or "", options)
        await recorder.message(
            role=MessageRole.assistant, content=f"[supervisor routes to: {choice}]",
            agent_id=agent.id, source_node_key=node_key,
            target_node_key=None if choice == "FINISH" else choice,
        )
        await recorder.event("step_end", {"node": node_key, "route": choice})
        return {"next": choice}

    return node


def make_conditional_router(node_key: str, edges: List, recorder, model: str) -> Callable:
    """LLM-judged routing across conditioned out-edges; returns a target key or FINISH."""
    targets = [e.target_node_key for e in edges]
    options = targets + ["FINISH"]
    branch_desc = "\n".join(
        f"- {e.target_node_key}: {e.condition or '(default / else)'}" for e in edges
    )

    async def router(state: RunState) -> str:
        sys = (
            "Decide which branch to take next based on the conversation.\n"
            f"Branches:\n{branch_desc}\n"
            f"Reply with EXACTLY one of: {', '.join(options)}."
        )
        msgs = [SystemMessage(content=sys)] + list(state.get("messages", []))
        resp, usage, provider = await ainvoke_chat(msgs, None, model)
        await recorder.usage(model, usage)
        choice = _match_choice(resp.content or "", options)
        await recorder.event("step_end", {"node": node_key, "route": choice, "via": "condition"})
        return choice

    return router
