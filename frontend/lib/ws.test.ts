import { describe, expect, it } from "vitest";
import { EMPTY_STREAM, foldEnvelope } from "./ws";
import type { RunStatus, WsEnvelope } from "./types";

const eventEnv = (id: number): WsEnvelope => ({
  kind: "event",
  run_id: 1,
  data: { id, type: "step_start", payload: {}, created_at: null },
});

const messageEnv = (id: number): WsEnvelope => ({
  kind: "message",
  run_id: 1,
  data: {
    id,
    role: "assistant",
    content: "hi",
    agent_id: null,
    source_node_key: null,
    target_node_key: null,
    tool_call_id: null,
    channel: null,
    direction: "internal",
    status: "pending",
    external_id: null,
    prompt_tokens: 0,
    completion_tokens: 0,
    cost_usd: 0,
    created_at: null,
  },
});

const statusEnv = (status: RunStatus): WsEnvelope => ({
  kind: "status",
  run_id: 1,
  data: { status, total_tokens: 42, total_cost_usd: 0.01, finished_at: "2026-01-01T00:00:00Z" },
});

describe("foldEnvelope", () => {
  it("appends events and dedupes by id (replays don't double-count)", () => {
    let s = foldEnvelope(EMPTY_STREAM, eventEnv(1));
    s = foldEnvelope(s, eventEnv(2));
    s = foldEnvelope(s, eventEnv(1));
    expect(s.events.map((e) => e.id)).toEqual([1, 2]);
  });

  it("appends messages and dedupes by id", () => {
    let s = foldEnvelope(EMPTY_STREAM, messageEnv(10));
    s = foldEnvelope(s, messageEnv(10));
    expect(s.messages).toHaveLength(1);
  });

  it("folds status totals", () => {
    const s = foldEnvelope(EMPTY_STREAM, statusEnv("completed"));
    expect(s.status).toBe("completed");
    expect(s.totalTokens).toBe(42);
    expect(s.totalCostUsd).toBe(0.01);
    expect(s.finishedAt).toBe("2026-01-01T00:00:00Z");
  });

  it("captures error envelopes", () => {
    const s = foldEnvelope(EMPTY_STREAM, {
      kind: "error",
      run_id: 1,
      data: { detail: "run not found" },
    });
    expect(s.error).toBe("run not found");
  });

  it("does not mutate the previous state", () => {
    const s1 = foldEnvelope(EMPTY_STREAM, eventEnv(1));
    expect(EMPTY_STREAM.events).toHaveLength(0);
    expect(s1).not.toBe(EMPTY_STREAM);
  });
});
