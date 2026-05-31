// Domain types mirroring the backend (models.py / schemas.py / agent_config.py).
// Kept hand-written so the app builds offline; run `npm run gen:api` to cross-check
// against the live OpenAPI schema when the backend changes.

export type RunStatus = "pending" | "running" | "completed" | "failed" | "cancelled";
export type MessageRole = "system" | "user" | "assistant" | "tool";
export type MessageDirection = "internal" | "inbound" | "outbound";
export type MessageStatus = "pending" | "sent" | "delivered" | "failed";
export type RunEventType =
  | "step_start"
  | "step_end"
  | "llm_chunk"
  | "tool_call"
  | "error"
  | "run_complete";
export type NodeType = "agent" | "supervisor";

export const TOOL_NAMES = ["web_search", "calculator", "http_fetch", "knowledge_search"] as const;
export type ToolName = (typeof TOOL_NAMES)[number];

// --- Agent config (typed JSON blocks) ---
export interface MemoryConfig {
  enabled: boolean;
  type: "none" | "buffer" | "summary";
  window: number | null;
  persist: boolean;
}
export interface AgentLimits {
  max_steps: number | null;
  max_tokens: number | null;
  max_cost_usd: number | null;
  timeout_seconds: number | null;
}
export interface Guardrails {
  blocked_topics: string[];
  allowed_tools_only: boolean;
  max_output_chars: number | null;
}
export interface InteractionRules {
  can_delegate: boolean;
  allowed_targets: string[];
  response_style: string | null;
}
export interface Schedule {
  type: "manual" | "interval" | "cron";
  expr: string | null;
  enabled: boolean;
}
export interface ChannelBinding {
  provider: "telegram" | "slack" | "whatsapp";
  enabled: boolean;
  config: Record<string, string>;
}

// --- Agent ---
export interface Agent {
  id: number;
  created_at: string;
  name: string;
  role: string;
  system_prompt: string;
  model: string;
  description: string | null;
  tools: string[];
  skills: string[];
  channels: ChannelBinding[];
  schedules: Schedule[];
  memory: MemoryConfig;
  interaction_rules: InteractionRules;
  guardrails: Guardrails;
  limits: AgentLimits;
}
export type AgentCreate = Omit<Agent, "id" | "created_at">;
export type AgentUpdate = Partial<AgentCreate>;

// --- Workflow graph ---
export interface WorkflowNode {
  id: number;
  workflow_id: number;
  agent_id: number;
  node_key: string;
  node_type: NodeType;
  position_x: number;
  position_y: number;
  label: string | null;
}
export interface WorkflowEdge {
  id: number;
  workflow_id: number;
  source_node_key: string;
  target_node_key: string;
  condition: string | null;
}
export interface Workflow {
  id: number;
  created_at: string;
  name: string;
  description: string | null;
  entry_node_key: string | null;
  is_template: boolean;
}
export interface WorkflowDetail extends Workflow {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}
export interface NodeInput {
  agent_id: number;
  node_key: string;
  node_type: NodeType;
  position_x: number;
  position_y: number;
  label?: string | null;
}
export interface EdgeInput {
  source_node_key: string;
  target_node_key: string;
  condition?: string | null;
}
export interface WorkflowCreate {
  name: string;
  description?: string | null;
  entry_node_key?: string | null;
  is_template?: boolean;
  nodes: NodeInput[];
  edges: EdgeInput[];
}
export type WorkflowUpdate = Partial<WorkflowCreate>;

// --- Runs / messages / events ---
export interface Message {
  id: number;
  created_at: string;
  run_id: number;
  role: MessageRole;
  content: string;
  agent_id: number | null;
  source_node_key: string | null;
  target_node_key: string | null;
  channel: string | null;
  direction: MessageDirection;
  status: MessageStatus;
  external_id: string | null;
  tool_call_id: string | null;
  prompt_tokens: number;
  completion_tokens: number;
  cost_usd: number;
}
export interface RunEvent {
  id: number;
  created_at: string;
  run_id: number;
  type: RunEventType;
  payload: Record<string, unknown>;
}
export interface Run {
  id: number;
  created_at: string;
  finished_at: string | null;
  workflow_id: number;
  status: RunStatus;
  input: string | null;
  output: string | null;
  error: string | null;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  total_cost_usd: number;
}
export interface RunDetail extends Run {
  messages: Message[];
  events: RunEvent[];
}
export interface RunCreate {
  workflow_id: number;
  input: string;
}

// --- Chats (web multi-turn conversations bound to a workflow) ---
export interface Chat {
  id: number;
  workflow_id: number;
  title: string;
  created_at: string;
  updated_at: string;
}
export interface ChatDetail extends Chat {
  runs: Run[]; // each run is one turn (input = user, output = assistant)
}
export interface ChatCreate {
  workflow_id: number;
  title?: string | null;
}

// --- Knowledge base (RAG) ---
export interface KnowledgeSource {
  source: string;
  chunks: number;
}
export interface KnowledgeUploadResult {
  results: KnowledgeSource[];
  total_chunks: number;
  skipped: string[];
}

// --- WebSocket envelopes (WS /ws/runs/{id}) — not in OpenAPI ---
export interface WsEventData {
  id: number;
  type: RunEventType;
  payload: Record<string, unknown>;
  created_at: string | null;
}
export interface WsMessageData {
  id: number;
  role: MessageRole;
  content: string;
  agent_id: number | null;
  source_node_key: string | null;
  target_node_key: string | null;
  tool_call_id: string | null;
  channel: string | null;
  direction: MessageDirection;
  status: MessageStatus;
  external_id: string | null;
  prompt_tokens: number;
  completion_tokens: number;
  cost_usd: number;
  created_at: string | null;
}
export interface WsStatusData {
  status: RunStatus;
  total_tokens: number;
  total_cost_usd: number;
  finished_at: string | null;
}
export type WsEnvelope =
  | { kind: "event"; run_id: number; data: WsEventData }
  | { kind: "message"; run_id: number; data: WsMessageData }
  | { kind: "status"; run_id: number; data: WsStatusData }
  | { kind: "error"; run_id: number; data: { detail: string } };
