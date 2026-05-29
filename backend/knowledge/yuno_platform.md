# Yuno AI Agents Orchestration Platform

Yuno is a platform for building, running, and monitoring multi-agent AI workflows.

## Core concepts
- **Agent**: a configurable AI worker with a name, role, system prompt, model, tools,
  and configuration (channels, schedules, memory, skills, interaction rules,
  guardrails, limits).
- **Workflow**: a directed graph of agent nodes connected by edges. Edges may carry
  conditions, and the graph may contain feedback loops. Each workflow has an entry node.
- **Run**: one execution of a workflow. Runs persist messages, events, and token/cost.

## Runtime
The runtime is built on **LangGraph**. A workflow stored in the database is compiled
into a LangGraph `StateGraph` at run time — the database row is the source of truth.
Agents call real tools and communicate with each other to complete tasks.

## LLM routing
The platform calls **Gemini 2.5 Flash** first and falls back to a local **Ollama/Qwen**
model if Gemini is unavailable or rate-limited.

## Tools
Built-in tools include web search, a calculator, HTTP fetch, and knowledge search
(retrieval-augmented generation over an ingested document collection).
