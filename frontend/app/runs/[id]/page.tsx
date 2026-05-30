"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/common/status-badge";
import { AnimatedNumber } from "@/components/common/animated-number";
import { MessageTimeline } from "@/components/monitor/message-timeline";
import { EventLog } from "@/components/monitor/event-log";
import { TokenCostChart } from "@/components/monitor/token-cost-chart";
import { qk, useRun, useWorkflows } from "@/lib/queries";
import { useRunStream } from "@/lib/ws";
import { fmtCost, fmtDateTime } from "@/lib/format";
import type { RunStatus, WsEventData, WsMessageData } from "@/lib/types";

const TERMINAL = new Set<RunStatus>(["completed", "failed", "cancelled"]);

function Card({ title, action, children }: { title?: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-border bg-card/60 p-4">
      {title ? (
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold">{title}</h3>
          {action}
        </div>
      ) : null}
      {children}
    </section>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-border bg-card/60 p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 font-mono text-xl font-semibold">{value}</p>
    </div>
  );
}

export default function RunMonitorPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const router = useRouter();

  const { data: run } = useRun(id);
  const stream = useRunStream(Number.isFinite(id) ? id : null);
  const { data: workflows } = useWorkflows();
  const qc = useQueryClient();

  // The WS status envelope carries no output/error, so once the run reaches a
  // terminal state refetch it to pull the authoritative output/error/finished_at.
  useEffect(() => {
    if (stream.status && TERMINAL.has(stream.status)) {
      qc.invalidateQueries({ queryKey: qk.run(id) });
    }
  }, [stream.status, id, qc]);

  const status: RunStatus = stream.status ?? run?.status ?? "pending";
  const tokens = stream.totalTokens || run?.total_tokens || 0;
  const cost = stream.totalCostUsd || run?.total_cost_usd || 0;
  const live = status === "running" || status === "pending";

  // Prefer the live stream; fall back to the persisted run (WS replays history anyway).
  const messages: WsMessageData[] = stream.messages.length
    ? stream.messages
    : (run?.messages ?? []).map((m) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        agent_id: m.agent_id,
        source_node_key: m.source_node_key,
        target_node_key: m.target_node_key,
        tool_call_id: m.tool_call_id,
        channel: m.channel,
        direction: m.direction,
        status: m.status,
        external_id: m.external_id,
        prompt_tokens: m.prompt_tokens,
        completion_tokens: m.completion_tokens,
        cost_usd: m.cost_usd,
        created_at: m.created_at,
      }));
  const events: WsEventData[] = stream.events.length
    ? stream.events
    : (run?.events ?? []).map((e) => ({
        id: e.id,
        type: e.type,
        payload: e.payload,
        created_at: e.created_at,
      }));

  const wfName = workflows?.find((w) => w.id === run?.workflow_id)?.name;

  return (
    <div className="mx-auto max-w-7xl space-y-5 px-6 py-8">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => router.push("/runs")}>
          <ArrowLeft className="size-4" />
        </Button>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h1 className="truncate text-xl font-semibold tracking-tight">
              {wfName ?? "Run"} <span className="font-mono text-muted-foreground">#{id}</span>
            </h1>
            {live && stream.connected ? (
              <span className="flex items-center gap-1.5 text-xs text-running">
                <span className="size-1.5 animate-pulse rounded-full bg-running" /> live
              </span>
            ) : null}
          </div>
          <p className="text-xs text-muted-foreground">
            started {fmtDateTime(run?.created_at)}
          </p>
        </div>
        <StatusBadge status={status} />
      </div>

      {stream.error ? (
        <div className="flex items-center gap-2 rounded-lg border border-failed/40 bg-failed/10 px-3 py-2 text-sm text-failed">
          <AlertTriangle className="size-4 shrink-0" />
          <span>{stream.error}</span>
        </div>
      ) : null}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat label="Total tokens" value={<AnimatedNumber value={tokens} />} />
        <Stat label="Cost" value={<AnimatedNumber value={cost} format={fmtCost} />} />
        <Stat label="Messages" value={messages.length} />
        <Stat label="Events" value={events.length} />
      </div>

      {run?.input ? (
        <Card title="Input">
          <p className="whitespace-pre-wrap text-sm text-muted-foreground">{run.input}</p>
        </Card>
      ) : null}

      {run?.output && status === "completed" ? (
        <Card title="Result">
          <p className="whitespace-pre-wrap text-sm">{run.output}</p>
        </Card>
      ) : null}

      {run?.error && status === "failed" ? (
        <Card title="Error">
          <p className="whitespace-pre-wrap text-sm text-failed">{run.error}</p>
        </Card>
      ) : null}

      <div className="grid gap-5 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card title="Inter-agent messages">
            <MessageTimeline messages={messages} />
          </Card>
        </div>
        <div className="space-y-5">
          <Card title="Token usage">
            <TokenCostChart messages={messages} />
          </Card>
          <Card title="Event log">
            <div className="max-h-96 overflow-y-auto scrollbar-thin">
              <EventLog events={events} />
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
