"use client";

import { useMemo } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Activity, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ConfirmButton } from "@/components/common/confirm-button";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader, PageShell } from "@/components/common/page-shell";
import { StatusBadge } from "@/components/common/status-badge";
import { fmtCost, fmtRelative, fmtTokens } from "@/lib/format";
import { useDeleteRun, useRuns, useWorkflows } from "@/lib/queries";

export default function RunsPage() {
  const router = useRouter();
  const { data: runs, isLoading } = useRuns();
  const { data: workflows } = useWorkflows();
  const del = useDeleteRun();
  const wfName = useMemo(
    () => new Map((workflows ?? []).map((w) => [w.id, w.name])),
    [workflows],
  );

  return (
    <PageShell>
      <PageHeader
        title="Runs"
        description="Workflow executions with live monitoring of logs, messages, and token/cost."
        action={
          <Button onClick={() => router.push("/runs/new")}>
            <Plus className="size-4" /> New run
          </Button>
        }
      />

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-14 rounded-lg" />
          ))}
        </div>
      ) : !runs?.length ? (
        <div className="rounded-xl border border-dashed border-border py-16 text-center">
          <Activity className="mx-auto size-8 text-muted-foreground/60" />
          <p className="mt-3 text-sm text-muted-foreground">No runs yet.</p>
          <Button className="mt-4" onClick={() => router.push("/runs/new")}>
            <Plus className="size-4" /> Start a run
          </Button>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-border">
          {runs.map((r, i) => {
            const open = () => router.push(`/runs/${r.id}`);
            return (
              <motion.div
                key={r.id}
                role="button"
                tabIndex={0}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.15, delay: Math.min(i * 0.02, 0.15) }}
                onClick={open}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    open();
                  }
                }}
                className="group flex w-full cursor-pointer items-center gap-4 border-b border-border bg-card px-4 py-3 text-left text-sm transition-colors last:border-0 hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <span className="w-12 font-mono text-xs text-muted-foreground">#{r.id}</span>
                <StatusBadge status={r.status} />
                <span className="min-w-0 flex-1 truncate">
                  {wfName.get(r.workflow_id) ?? `Workflow #${r.workflow_id}`}
                </span>
                <span className="hidden w-24 text-right font-mono text-xs text-muted-foreground sm:block">
                  {fmtTokens(r.total_tokens)} tok
                </span>
                <span className="hidden w-20 text-right font-mono text-xs text-muted-foreground sm:block">
                  {fmtCost(r.total_cost_usd)}
                </span>
                <span className="w-20 text-right text-xs text-muted-foreground">
                  {fmtRelative(r.created_at)}
                </span>
                <ConfirmButton
                  variant="ghost"
                  size="icon-sm"
                  className="text-failed opacity-0 transition-opacity group-hover:opacity-100 hover:text-failed"
                  confirmLabel="?"
                  onConfirm={() => del.mutate(r.id)}
                  aria-label={`Delete run #${r.id}`}
                >
                  <Trash2 className="size-3.5" />
                </ConfirmButton>
              </motion.div>
            );
          })}
        </div>
      )}
    </PageShell>
  );
}
