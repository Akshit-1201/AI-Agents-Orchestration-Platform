"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, ApiError } from "./api";
import type {
  AgentCreate,
  AgentUpdate,
  ChatCreate,
  RunCreate,
  WorkflowCreate,
  WorkflowUpdate,
} from "./types";

export const qk = {
  agents: ["agents"] as const,
  agent: (id: number) => ["agents", id] as const,
  workflows: ["workflows"] as const,
  workflow: (id: number) => ["workflows", id] as const,
  runs: ["runs"] as const,
  run: (id: number) => ["runs", id] as const,
  chats: ["chats"] as const,
  chat: (id: number) => ["chats", id] as const,
  knowledge: ["knowledge"] as const,
};

const errMsg = (e: unknown) =>
  e instanceof ApiError ? e.message : "Could not reach the server — is the backend running?";

// --------------------------- Agents ---------------------------
export const useAgents = () =>
  useQuery({ queryKey: qk.agents, queryFn: api.listAgents });

export const useAgent = (id: number) =>
  useQuery({
    queryKey: qk.agent(id),
    queryFn: () => api.getAgent(id),
    enabled: Number.isFinite(id) && id > 0,
  });

export function useCreateAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: AgentCreate) => api.createAgent(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.agents });
      toast.success("Agent created");
    },
    onError: (e) => toast.error(errMsg(e)),
  });
}

export function useUpdateAgent(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: AgentUpdate) => api.updateAgent(id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.agents });
      qc.invalidateQueries({ queryKey: qk.agent(id) });
      toast.success("Agent saved");
    },
    onError: (e) => toast.error(errMsg(e)),
  });
}

export function useDeleteAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteAgent(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.agents });
      toast.success("Agent deleted");
    },
    onError: (e) => toast.error(errMsg(e)),
  });
}

// --------------------------- Workflows ---------------------------
export const useWorkflows = () =>
  useQuery({ queryKey: qk.workflows, queryFn: api.listWorkflows });

export const useWorkflow = (id: number) =>
  useQuery({
    queryKey: qk.workflow(id),
    queryFn: () => api.getWorkflow(id),
    enabled: Number.isFinite(id) && id > 0,
  });

export function useCreateWorkflow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: WorkflowCreate) => api.createWorkflow(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.workflows });
      toast.success("Workflow created");
    },
    onError: (e) => toast.error(errMsg(e)),
  });
}

export function useUpdateWorkflow(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: WorkflowUpdate) => api.updateWorkflow(id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.workflows });
      qc.invalidateQueries({ queryKey: qk.workflow(id) });
      toast.success("Workflow saved");
    },
    onError: (e) => toast.error(errMsg(e)),
  });
}

export function useDeleteWorkflow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteWorkflow(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.workflows });
      toast.success("Workflow deleted");
    },
    onError: (e) => toast.error(errMsg(e)),
  });
}

// --------------------------- Runs ---------------------------
export const useRuns = () =>
  useQuery({ queryKey: qk.runs, queryFn: api.listRuns });

export const useRun = (id: number) =>
  useQuery({
    queryKey: qk.run(id),
    queryFn: () => api.getRun(id),
    enabled: Number.isFinite(id) && id > 0,
  });

export function useCreateRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ body, wait }: { body: RunCreate; wait?: boolean }) =>
      api.createRun(body, wait),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.runs });
    },
    onError: (e) => toast.error(errMsg(e)),
  });
}

export function useDeleteRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteRun(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.runs });
      toast.success("Run deleted");
    },
    onError: (e) => toast.error(errMsg(e)),
  });
}

// --------------------------- Chats ---------------------------
export const useChats = () =>
  useQuery({ queryKey: qk.chats, queryFn: api.listChats });

export const useChat = (id: number) =>
  useQuery({
    queryKey: qk.chat(id),
    queryFn: () => api.getChat(id),
    enabled: Number.isFinite(id) && id > 0,
  });

export function useCreateChat() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ChatCreate) => api.createChat(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.chats }),
    onError: (e) => toast.error(errMsg(e)),
  });
}

export function useDeleteChat() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteChat(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.chats });
      toast.success("Chat deleted");
    },
    onError: (e) => toast.error(errMsg(e)),
  });
}

// --------------------------- Knowledge base (RAG) ---------------------------
export const useKnowledge = () =>
  useQuery({ queryKey: qk.knowledge, queryFn: api.listKnowledge });

export function useUploadKnowledge() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (files: File[]) => api.uploadKnowledge(files),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: qk.knowledge });
      const n = res.total_chunks;
      const skip = res.skipped.length ? ` · ${res.skipped.length} skipped (no text)` : "";
      toast.success(`Ingested ${n} chunk${n === 1 ? "" : "s"}${skip}`);
    },
    onError: (e) => toast.error(errMsg(e)),
  });
}

export function useDeleteKnowledge() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (source: string) => api.deleteKnowledge(source),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.knowledge });
      toast.success("Document removed");
    },
    onError: (e) => toast.error(errMsg(e)),
  });
}

export function useSendChatMessage(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: string) => api.sendChatMessage(id, input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.chat(id) });
      qc.invalidateQueries({ queryKey: qk.chats });
    },
    onError: (e) => toast.error(errMsg(e)),
  });
}
