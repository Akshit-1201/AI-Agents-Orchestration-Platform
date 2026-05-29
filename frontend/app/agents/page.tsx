"use client";

import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Bot, Pencil, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader, PageShell } from "@/components/common/page-shell";
import { ConfirmButton } from "@/components/common/confirm-button";
import { useAgents, useDeleteAgent } from "@/lib/queries";

export default function AgentsPage() {
  const router = useRouter();
  const { data: agents, isLoading } = useAgents();
  const del = useDeleteAgent();

  return (
    <PageShell>
      <PageHeader
        title="Agents"
        description="Configurable AI agents — identity, tools, memory, guardrails, limits."
        action={
          <Button onClick={() => router.push("/agents/new")}>
            <Plus className="size-4" /> New agent
          </Button>
        }
      />

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-40 rounded-xl" />
          ))}
        </div>
      ) : !agents?.length ? (
        <div className="rounded-xl border border-dashed border-border py-16 text-center">
          <Bot className="mx-auto size-8 text-muted-foreground/60" />
          <p className="mt-3 text-sm text-muted-foreground">No agents yet.</p>
          <Button className="mt-4" onClick={() => router.push("/agents/new")}>
            <Plus className="size-4" /> Create your first agent
          </Button>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {agents.map((a, i) => (
            <motion.div
              key={a.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2, delay: Math.min(i * 0.03, 0.2) }}
              className="group flex flex-col rounded-xl border border-border bg-card/60 p-4 transition-colors hover:border-border/80 hover:bg-card"
            >
              <div className="flex items-start gap-3">
                <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-brand/15 text-brand">
                  <Bot className="size-4.5" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{a.name}</p>
                  <p className="truncate text-xs text-muted-foreground">{a.role}</p>
                </div>
              </div>
              <p className="mt-3 font-mono text-xs text-muted-foreground">{a.model}</p>
              {a.tools.length ? (
                <div className="mt-2 flex flex-wrap gap-1">
                  {a.tools.map((t) => (
                    <span key={t} className="rounded border border-border px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                      {t}
                    </span>
                  ))}
                </div>
              ) : null}
              <div className="mt-4 flex items-center gap-1 border-t border-border pt-3 opacity-0 transition-opacity group-hover:opacity-100">
                <Button variant="ghost" size="sm" onClick={() => router.push(`/agents/${a.id}`)}>
                  <Pencil className="size-3.5" /> Edit
                </Button>
                <ConfirmButton
                  variant="ghost"
                  size="sm"
                  className="text-failed hover:text-failed"
                  onConfirm={() => del.mutate(a.id)}
                >
                  <Trash2 className="size-3.5" /> Delete
                </ConfirmButton>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </PageShell>
  );
}
