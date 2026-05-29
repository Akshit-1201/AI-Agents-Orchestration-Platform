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
}

const EMPTY: RunStreamState = {
  connected: false,
  events: [],
  messages: [],
  status: null,
  totalTokens: 0,
  totalCostUsd: 0,
  finishedAt: null,
};

/**
 * Subscribes to WS /ws/runs/{id} and folds the streamed envelopes
 * (events + messages + status) into a single reactive state. The server replays
 * persisted history on connect, then streams live and closes on a terminal status.
 */
export function useRunStream(runId: number | null): RunStreamState {
  const [state, setState] = useState<RunStreamState>(EMPTY);

  useEffect(() => {
    if (runId == null) return;
    setState(EMPTY);

    const ws = new WebSocket(`${WS_BASE}/ws/runs/${runId}`);
    const seenEvents = new Set<number>();
    const seenMessages = new Set<number>();

    ws.onopen = () => setState((s) => ({ ...s, connected: true }));
    ws.onclose = () => setState((s) => ({ ...s, connected: false }));
    ws.onmessage = (ev) => {
      let env: WsEnvelope;
      try {
        env = JSON.parse(ev.data);
      } catch {
        return;
      }
      setState((s) => {
        if (env.kind === "event") {
          if (seenEvents.has(env.data.id)) return s;
          seenEvents.add(env.data.id);
          return { ...s, events: [...s.events, env.data] };
        }
        if (env.kind === "message") {
          if (seenMessages.has(env.data.id)) return s;
          seenMessages.add(env.data.id);
          return { ...s, messages: [...s.messages, env.data] };
        }
        if (env.kind === "status") {
          return {
            ...s,
            status: env.data.status,
            totalTokens: env.data.total_tokens,
            totalCostUsd: env.data.total_cost_usd,
            finishedAt: env.data.finished_at,
          };
        }
        return s;
      });
    };

    return () => ws.close();
  }, [runId]);

  return state;
}
