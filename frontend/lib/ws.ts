"use client";

import { useEffect, useState } from "react";
import { WS_BASE } from "./api";
import type { RunStatus, WsEnvelope, WsEventData, WsMessageData } from "./types";

export interface RunStreamState {
  connected: boolean;
  events: WsEventData[];
  messages: WsMessageData[];
  status: RunStatus | null;
  totalTokens: number;
  totalCostUsd: number;
  finishedAt: string | null;
  error: string | null;
}

export const EMPTY_STREAM: RunStreamState = {
  connected: false,
  events: [],
  messages: [],
  status: null,
  totalTokens: 0,
  totalCostUsd: 0,
  finishedAt: null,
  error: null,
};

const TERMINAL: ReadonlySet<RunStatus> = new Set(["completed", "failed", "cancelled"]);
const MAX_RETRIES = 3;

/**
 * Pure reducer: folds one WS envelope into the stream state. Events/messages are
 * deduped by id (the server replays history on every (re)connect), so this stays
 * correct across reconnects. Exported for unit testing.
 */
export function foldEnvelope(state: RunStreamState, env: WsEnvelope): RunStreamState {
  switch (env.kind) {
    case "event":
      if (state.events.some((e) => e.id === env.data.id)) return state;
      return { ...state, events: [...state.events, env.data] };
    case "message":
      if (state.messages.some((m) => m.id === env.data.id)) return state;
      return { ...state, messages: [...state.messages, env.data] };
    case "status":
      return {
        ...state,
        status: env.data.status,
        totalTokens: env.data.total_tokens,
        totalCostUsd: env.data.total_cost_usd,
        finishedAt: env.data.finished_at,
      };
    case "error":
      return { ...state, error: env.data.detail };
    default:
      return state;
  }
}

/**
 * Subscribes to WS /ws/runs/{id} and folds the streamed envelopes (events +
 * messages + status + error) into a single reactive state. The server replays
 * persisted history on connect, then streams live and closes on a terminal status.
 * If the socket drops before a terminal status, it auto-reconnects (bounded).
 */
export function useRunStream(runId: number | null): RunStreamState {
  const [state, setState] = useState<RunStreamState>(EMPTY_STREAM);
  const [trackedRunId, setTrackedRunId] = useState(runId);

  // Reset the stream when the run changes. Adjusting state during render (rather
  // than in an effect) is React's recommended pattern and avoids a cascading render.
  if (runId !== trackedRunId) {
    setTrackedRunId(runId);
    setState(EMPTY_STREAM);
  }

  useEffect(() => {
    if (runId == null) return;

    let ws: WebSocket | undefined;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let attempts = 0;
    let closedByUs = false; // unmount / runId change
    let done = false; // terminal status or fatal error -> stop reconnecting

    const connect = () => {
      ws = new WebSocket(`${WS_BASE}/ws/runs/${runId}`);

      ws.onopen = () => {
        attempts = 0;
        setState((s) => ({ ...s, connected: true, error: null }));
      };

      ws.onmessage = (ev) => {
        let env: WsEnvelope;
        try {
          env = JSON.parse(ev.data);
        } catch {
          return;
        }
        if (env.kind === "error") done = true;
        if (env.kind === "status" && TERMINAL.has(env.data.status)) done = true;
        setState((s) => foldEnvelope(s, env));
      };

      ws.onerror = () => {
        // Intentionally a no-op. A `close` event ALWAYS follows an `error`, and `onclose`
        // already owns reconnect + user-facing messaging (and ignores a socket we aborted
        // ourselves via `closedByUs`). Surfacing an error here caused a red, failure-looking
        // banner to flash on every fresh monitor mount: React StrictMode (dev) mounts the
        // effect, immediately aborts the first socket, and remounts — the aborted socket's
        // `error` event would set "connection error" before the real socket finished opening.
      };

      ws.onclose = () => {
        setState((s) => ({ ...s, connected: false }));
        if (closedByUs || done) return;
        if (attempts < MAX_RETRIES) {
          attempts += 1;
          setState((s) => ({ ...s, error: `connection lost — reconnecting (${attempts}/${MAX_RETRIES})…` }));
          retryTimer = setTimeout(connect, 500 * attempts);
        } else {
          setState((s) => ({ ...s, error: "connection lost — could not reconnect" }));
        }
      };
    };

    connect();

    return () => {
      closedByUs = true;
      if (retryTimer) clearTimeout(retryTimer);
      ws?.close();
    };
  }, [runId]);

  return state;
}
