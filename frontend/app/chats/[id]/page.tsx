"use client";

import { useEffect, useMemo, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ChatThread } from "@/components/chat/chat-thread";
import { ChatComposer } from "@/components/chat/chat-composer";
import { qk, useChat, useSendChatMessage, useWorkflows } from "@/lib/queries";
import { useRunStream } from "@/lib/ws";
import type { RunStatus } from "@/lib/types";

const TERMINAL = new Set<RunStatus>(["completed", "failed", "cancelled"]);

export default function ChatPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const router = useRouter();
  const qc = useQueryClient();

  const { data: chat } = useChat(Number.isFinite(id) ? id : 0);
  const { data: workflows } = useWorkflows();
  const send = useSendChatMessage(id);

  const runs = useMemo(
    () => [...(chat?.runs ?? [])].sort((a, b) => a.id - b.id),
    [chat],
  );

  // Derive the in-flight turn from the thread itself (no extra state): the last run that
  // hasn't reached a terminal status. Stream it; it clears itself once it completes.
  const lastRun = runs[runs.length - 1];
  const activeRunId = lastRun && !TERMINAL.has(lastRun.status) ? lastRun.id : null;
  const stream = useRunStream(activeRunId);

  // When the in-flight turn ends, pull the finalized run (output/tokens). Pure side effect
  // (no setState) so it doesn't trigger cascading renders.
  useEffect(() => {
    if (activeRunId != null && stream.status && TERMINAL.has(stream.status)) {
      qc.invalidateQueries({ queryKey: qk.chat(id) });
    }
  }, [stream.status, activeRunId, id, qc]);

  // Optimistic user bubble while the POST is in flight (before the run row arrives).
  const optimistic = send.isPending ? send.variables ?? null : null;
  const busy = activeRunId != null || send.isPending;

  // Autoscroll to the newest content as the conversation grows / streams.
  const bottomRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [runs.length, send.isPending, stream.messages.length]);

  const wfName = workflows?.find((w) => w.id === chat?.workflow_id)?.name;

  return (
    <div className="mx-auto flex h-screen w-full max-w-3xl flex-col px-4 py-4">
      <div className="flex items-center gap-3 pb-3">
        <Button variant="ghost" size="icon" onClick={() => router.push("/chats")}>
          <ArrowLeft className="size-4" />
        </Button>
        <div className="min-w-0">
          <h1 className="truncate text-base font-semibold">{chat?.title ?? "Chat"}</h1>
          <p className="truncate text-xs text-muted-foreground">
            {wfName ?? (chat ? `Workflow #${chat.workflow_id}` : "")}
          </p>
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-border bg-card/40">
        <div className="min-h-0 flex-1 overflow-y-auto scrollbar-thin p-4">
          <ChatThread runs={runs} activeRunId={activeRunId} stream={stream} optimistic={optimistic} />
          <div ref={bottomRef} />
        </div>
        <ChatComposer onSend={(text) => send.mutate(text)} disabled={busy} />
      </div>
    </div>
  );
}
