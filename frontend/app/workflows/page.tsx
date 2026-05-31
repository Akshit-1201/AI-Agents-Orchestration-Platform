"use client";

import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Plus, Trash2, Workflow as WorkflowIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader, PageShell } from "@/components/common/page-shell";
import { ConfirmButton } from "@/components/common/confirm-button";
import { fmtRelative } from "@/lib/format";
import { useDeleteWorkflow, useWorkflows } from "@/lib/queries";

export default function WorkflowsPage() {
  const router = useRouter();
  const { data: workflows, isLoading } = useWorkflows();
  const del = useDeleteWorkflow();

  return (
    <PageShell>
      <PageHeader
        title="Workflows"
        description="Connect agents into collaborative graphs with conditions and feedback loops."
        action={
          <Button onClick={() => router.push("/workflows/new")}>
            <Plus className="size-4" /> New workflow
          </Button>
        }
      />

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-20 rounded-xl" />
          ))}
        </div>
      ) : !workflows?.length ? (
        <div className="rounded-xl border border-dashed border-border py-16 text-center">
          <WorkflowIcon className="mx-auto size-8 text-muted-foreground/60" />
          <p className="mt-3 text-sm text-muted-foreground">No workflows yet.</p>
          <Button className="mt-4" onClick={() => router.push("/workflows/new")}>
            <Plus className="size-4" /> Create your first workflow
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          {workflows.map((w, i) => {
            const open = () => router.push(`/workflows/${w.id}`);
            return (
            <motion.div
              key={w.id}
              role="button"
              tabIndex={0}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.18, delay: Math.min(i * 0.03, 0.2) }}
              onClick={open}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  open();
                }
              }}
              className="group flex w-full cursor-pointer items-center gap-4 rounded-xl border border-border bg-card p-4 text-left transition-colors hover:border-foreground/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-brand/15 text-brand">
                <WorkflowIcon className="size-5" />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <p className="truncate font-semibold">{w.name}</p>
                  {w.is_template ? (
                    <span className="rounded border border-border px-1.5 py-0.5 text-[10px] text-muted-foreground">
                      template
                    </span>
                  ) : null}
                </div>
                <p className="truncate text-xs text-muted-foreground">
                  {w.description || "No description"} · {fmtRelative(w.created_at)}
                </p>
              </div>
              <ConfirmButton
                variant="ghost"
                size="sm"
                className="text-failed opacity-0 transition-opacity group-hover:opacity-100 hover:text-failed"
                onConfirm={() => del.mutate(w.id)}
              >
                <Trash2 className="size-3.5" /> Delete
              </ConfirmButton>
            </motion.div>
            );
          })}
        </div>
      )}
    </PageShell>
  );
}
