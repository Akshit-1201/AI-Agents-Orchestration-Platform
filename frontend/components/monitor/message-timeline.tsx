"use client";

import { AnimatePresence, motion } from "framer-motion";
import { ROLE_COLOR } from "@/lib/status";
import type { WsMessageData } from "@/lib/types";

export function MessageTimeline({ messages }: { messages: WsMessageData[] }) {
  if (!messages.length) {
    return <p className="py-8 text-center text-sm text-muted-foreground">No messages yet.</p>;
  }
  return (
    <div className="space-y-2">
      <AnimatePresence initial={false}>
        {messages.map((m) => {
          const color = ROLE_COLOR[m.role] ?? "#94a3b8";
          const tokens = m.prompt_tokens + m.completion_tokens;
          return (
            <motion.div
              key={m.id}
              layout
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2 }}
              className="rounded-lg border border-border bg-card/50 p-3"
            >
              <div className="flex items-center gap-2 text-xs">
                <span
                  className="rounded px-1.5 py-0.5 font-mono"
                  style={{ color, backgroundColor: `${color}1a` }}
                >
                  {m.role}
                </span>
                {m.channel || m.direction !== "internal" ? (
                  <span className="rounded px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide text-muted-foreground ring-1 ring-inset ring-border">
                    {m.channel ?? "channel"} · {m.direction}
                  </span>
                ) : null}
                {m.source_node_key ? (
                  <span className="font-mono text-muted-foreground">
                    {m.source_node_key}
                    {m.target_node_key ? ` → ${m.target_node_key}` : ""}
                  </span>
                ) : null}
                {tokens > 0 ? (
                  <span className="ml-auto font-mono text-muted-foreground">{tokens} tok</span>
                ) : null}
              </div>
              <p className="mt-1.5 whitespace-pre-wrap break-words text-sm">{m.content}</p>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
