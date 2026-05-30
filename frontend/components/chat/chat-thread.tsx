"use client";

import { Bot, User } from "lucide-react";
import { cn } from "@/lib/utils";
import { fmtCost } from "@/lib/format";
import type { Run } from "@/lib/types";
import type { RunStreamState } from "@/lib/ws";

function TypingDots() {
  return (
    <span className="inline-flex items-center gap-1 py-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="size-1.5 animate-pulse rounded-full bg-current"
          style={{ animationDelay: `${i * 160}ms` }}
        />
      ))}
    </span>
  );
}

function Bubble({
  role,
  children,
}: {
  role: "user" | "assistant";
  children: React.ReactNode;
}) {
  const isUser = role === "user";
  return (
    <div className={cn("flex gap-2.5", isUser ? "flex-row-reverse" : "flex-row")}>
      <span
        className={cn(
          "mt-0.5 grid size-7 shrink-0 place-items-center rounded-full",
          isUser ? "bg-primary/15 text-primary" : "bg-brand/15 text-brand",
        )}
      >
        {isUser ? <User className="size-3.5" /> : <Bot className="size-3.5" />}
      </span>
      <div
        className={cn(
          "max-w-[80%] rounded-2xl px-3.5 py-2 text-sm",
          isUser
            ? "rounded-tr-sm bg-primary text-primary-foreground"
            : "rounded-tl-sm border border-border bg-card",
        )}
      >
        {children}
      </div>
    </div>
  );
}

/** Latest streamed assistant text for the in-flight run (per-node messages arrive live). */
function liveAssistantText(s: RunStreamState): string {
  const msgs = s.messages.filter((m) => m.role === "assistant" && m.content.trim());
  return msgs.length ? msgs[msgs.length - 1].content : "";
}

export function ChatThread({
  runs,
  activeRunId,
  stream,
  optimistic,
}: {
  runs: Run[];
  activeRunId: number | null;
  stream: RunStreamState;
  optimistic: string | null;
}) {
  return (
    <div className="space-y-4">
      {runs.length === 0 && optimistic == null ? (
        <p className="py-10 text-center text-sm text-muted-foreground">
          Send a message to start the conversation.
        </p>
      ) : null}

      {runs.map((r) => {
        const live = r.id === activeRunId && r.status !== "completed";
        const completed = r.status === "completed";
        const failed = r.status === "failed";
        const text = live ? liveAssistantText(stream) : r.output ?? "";
        return (
          <div key={r.id} className="space-y-4">
            <Bubble role="user">
              <p className="whitespace-pre-wrap">{r.input}</p>
            </Bubble>
            <Bubble role="assistant">
              {failed ? (
                <p className="whitespace-pre-wrap text-failed">{r.error || "The run failed."}</p>
              ) : text ? (
                <p className="whitespace-pre-wrap">{text}</p>
              ) : completed ? (
                <p className="text-muted-foreground">(no output)</p>
              ) : (
                <span className="text-muted-foreground">
                  <TypingDots />
                </span>
              )}
              {completed ? (
                <p className="mt-1.5 font-mono text-[10px] text-muted-foreground">
                  run #{r.id} · {r.total_tokens} tok · {fmtCost(r.total_cost_usd)}
                </p>
              ) : null}
            </Bubble>
          </div>
        );
      })}

      {optimistic != null ? (
        <div className="space-y-4">
          <Bubble role="user">
            <p className="whitespace-pre-wrap">{optimistic}</p>
          </Bubble>
          <Bubble role="assistant">
            <span className="text-muted-foreground">
              <TypingDots />
            </span>
          </Bubble>
        </div>
      ) : null}
    </div>
  );
}
