"use client";

import { AnimatePresence, motion } from "framer-motion";
import type { WsEventData } from "@/lib/types";

// Theme-aware via CSS vars (these are used as a plain inline `color`).
const TYPE_COLOR: Record<string, string> = {
  step_start: "var(--color-running)",
  step_end: "var(--color-cancelled)",
  llm_chunk: "var(--color-chart-4)",
  tool_call: "var(--color-pending)",
  error: "var(--color-failed)",
  run_complete: "var(--color-completed)",
};

function summarize(e: WsEventData): string {
  const p = (e.payload ?? {}) as Record<string, unknown>;
  if (e.type === "tool_call") {
    const result = String(p.result ?? "");
    return `${p.tool}(${JSON.stringify(p.args ?? {})}) → ${result.slice(0, 60)}`;
  }
  if (e.type === "error") return String(p.error ?? "error");
  const bits: string[] = [];
  if (p.node) bits.push(`node ${p.node}`);
  if (p.provider) bits.push(String(p.provider));
  if (p.route) bits.push(`→ ${p.route}`);
  if (p.stopped) bits.push(`stopped: ${p.stopped}`);
  return bits.join(" · ") || JSON.stringify(p).slice(0, 80);
}

export function EventLog({ events }: { events: WsEventData[] }) {
  if (!events.length) {
    return <p className="py-8 text-center text-sm text-muted-foreground">No events yet.</p>;
  }
  return (
    <div className="space-y-1 font-mono text-xs">
      <AnimatePresence initial={false}>
        {events.map((e) => (
          <motion.div
            key={e.id}
            layout
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.18 }}
            className="flex items-start gap-2"
          >
            <span className="shrink-0" style={{ color: TYPE_COLOR[e.type] ?? "var(--color-muted-foreground)" }}>
              {e.type}
            </span>
            <span className="min-w-0 flex-1 truncate text-muted-foreground">{summarize(e)}</span>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
