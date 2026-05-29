import type {
  Agent,
  AgentCreate,
  AgentUpdate,
  Run,
  RunCreate,
  RunDetail,
  Workflow,
  WorkflowCreate,
  WorkflowDetail,
  WorkflowUpdate,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
export const WS_BASE = API_BASE.replace(/^http/, "ws");

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail =
        typeof body?.detail === "string"
          ? body.detail
          : JSON.stringify(body?.detail ?? body);
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  // agents
  listAgents: () => request<Agent[]>("/agents"),
  getAgent: (id: number) => request<Agent>(`/agents/${id}`),
  createAgent: (body: AgentCreate) =>
    request<Agent>("/agents", { method: "POST", body: JSON.stringify(body) }),
  updateAgent: (id: number, body: AgentUpdate) =>
    request<Agent>(`/agents/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteAgent: (id: number) =>
    request<void>(`/agents/${id}`, { method: "DELETE" }),

  // workflows
  listWorkflows: () => request<Workflow[]>("/workflows"),
  getWorkflow: (id: number) => request<WorkflowDetail>(`/workflows/${id}`),
  createWorkflow: (body: WorkflowCreate) =>
    request<WorkflowDetail>("/workflows", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateWorkflow: (id: number, body: WorkflowUpdate) =>
    request<WorkflowDetail>(`/workflows/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  deleteWorkflow: (id: number) =>
    request<void>(`/workflows/${id}`, { method: "DELETE" }),

  // runs
  listRuns: () => request<Run[]>("/runs"),
  getRun: (id: number) => request<RunDetail>(`/runs/${id}`),
  createRun: (body: RunCreate, wait = false) =>
    request<RunDetail>(`/runs${wait ? "?wait=true" : ""}`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
