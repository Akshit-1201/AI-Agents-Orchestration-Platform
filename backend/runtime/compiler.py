"""Compile a DB workflow definition into a runnable LangGraph StateGraph.

The DB row is the source of truth — this materializes a fresh graph per run. Edges are
honored as written: a node with one plain out-edge gets a static edge; supervisor nodes
(and nodes with multiple out-edges) get conditional edges routed on state['next'];
nodes with no out-edge route to END. Cycles (feedback loops) are allowed and capped by
the graph recursion limit set in the executor.
"""
import logging
from typing import Dict, List

from langgraph.graph import END, START, StateGraph

from models import Agent, NodeType, Workflow
from runtime.nodes import make_agent_node, make_conditional_router, make_supervisor_node
from runtime.state import RunState
from runtime.tools import get_tools_for

logger = logging.getLogger("yuno.runtime.compiler")


def compile_workflow(workflow: Workflow, agents_by_id: Dict[int, Agent], recorder, checkpointer=None):
    nodes = list(workflow.nodes)
    if not nodes:
        raise ValueError("workflow has no nodes")

    out_edges: Dict[str, List] = {n.node_key: [] for n in nodes}
    for e in workflow.edges:
        out_edges.setdefault(e.source_node_key, []).append(e)

    entry_key = workflow.entry_node_key or nodes[0].node_key

    builder = StateGraph(RunState)
    for n in nodes:
        agent = agents_by_id[n.agent_id]
        if n.node_type == NodeType.supervisor:
            successors = [e.target_node_key for e in out_edges.get(n.node_key, [])]
            builder.add_node(n.node_key, make_supervisor_node(agent, n.node_key, successors, recorder))
        else:
            builder.add_node(
                n.node_key,
                make_agent_node(
                    agent, n.node_key, get_tools_for(agent.tools), recorder,
                    is_entry=(n.node_key == entry_key),
                ),
            )

    builder.add_edge(START, workflow.entry_node_key or nodes[0].node_key)

    for n in nodes:
        outs = out_edges.get(n.node_key, [])
        if n.node_type == NodeType.supervisor:
            # supervisor sets state['next']; route on it
            mapping = {e.target_node_key: e.target_node_key for e in outs}
            mapping["FINISH"] = END
            builder.add_conditional_edges(n.node_key, _make_router("FINISH"), mapping)
        elif len(outs) > 1 and any(e.condition for e in outs):
            # LLM-judged conditional routing across the conditioned branches
            agent = agents_by_id[n.agent_id]
            mapping = {e.target_node_key: e.target_node_key for e in outs}
            mapping["FINISH"] = END
            builder.add_conditional_edges(
                n.node_key, make_conditional_router(n.node_key, outs, recorder, agent.model), mapping
            )
        elif len(outs) > 1:
            # plain fan-out with no conditions: follow state['next'] else the first edge
            mapping = {e.target_node_key: e.target_node_key for e in outs}
            mapping["FINISH"] = END
            builder.add_conditional_edges(n.node_key, _make_router(outs[0].target_node_key), mapping)
        elif len(outs) == 1:
            builder.add_edge(n.node_key, outs[0].target_node_key)
        else:
            builder.add_edge(n.node_key, END)

    return builder.compile(checkpointer=checkpointer)


def _make_router(default: str):
    """Route on state['next'] (set by a supervisor); else take the default successor."""

    def router(state: RunState) -> str:
        return state.get("next") or default

    return router
