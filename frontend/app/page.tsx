"use client";

import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Activity, Bot, Plus, Workflow } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageHeader, PageShell } from "@/components/common/page-shell";
import { StatusBadge } from "@/components/common/status-badge";
import { fmtCost, fmtRelative, fmtTokens } from "@/lib/format";
import { useAgents, useRuns, useWorkflows } from "@/lib/queries";

export default function DashboardPage() {
  const router = useRouter();
  const agents = useAgents();
  const workflows = useWorkflows();
  const runs = useRuns();

  const stats = [
    { label: "Agents", value: agents.data?.length ?? 0, icon: Bot, href: "/agents" },
    { label: "Workflows", value: workflows.data?.length ?? 0, icon: Workflow, href: "/workflows" },
    { label: "Runs", value: runs.data?.length ?? 0, icon: Activity, href: "/runs" },
  ];
  const recent = (runs.data ?? []).slice(0, 6);

  return (
    <PageShell>
      <PageHeader
        title="Dashboard"
        description="Build configurable agents, connect them into workflows, run and monitor them live."
        action={
          <Button onClick={() => router.push("/runs/new")}>
            <Plus className="size-4" /> New run
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-3">
        {stats.map(({ label, value, icon: Icon, href }, i) => (
          <motion.button
            key={label}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2, delay: i * 0.04 }}
            onClick={() => router.push(href)}
            className="flex items-center gap-4 rounded-xl border border-border bg-card/60 p-5 text-left transition-colors hover:border-border/80 hover:bg-card"
          >
            <span className="grid size-11 place-items-center rounded-lg bg-brand/15 text-brand">
              <Icon className="size-5" />
            </span>
            <div>
              <p className="font-mono text-2xl font-semibold">{value}</p>
              <p className="text-sm text-muted-foreground">{label}</p>
            </div>
          </motion.button>
        ))}
      </div>

      <section className="rounded-xl border border-border bg-card/60 p-5">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold">Recent runs</h3>
          <Button variant="ghost" size="sm" onClick={() => router.push("/runs")}>
            View all
          </Button>
        </div>
        {recent.length ? (
          <div className="divide-y divide-border">
            {recent.map((r) => (
              <button
                key={r.id}
                onClick={() => router.push(`/runs/${r.id}`)}
                className="flex w-full items-center gap-3 py-2.5 text-left text-sm transition-colors hover:opacity-80"
              >
                <span className="w-10 font-mono text-xs text-muted-foreground">#{r.id}</span>
                <StatusBadge status={r.status} />
                <span className="ml-auto font-mono text-xs text-muted-foreground">
                  {fmtTokens(r.total_tokens)} tok · {fmtCost(r.total_cost_usd)}
                </span>
                <span className="w-20 text-right text-xs text-muted-foreground">
                  {fmtRelative(r.created_at)}
                </span>
              </button>
            ))}
          </div>
        ) : (
          <p className="py-6 text-center text-sm text-muted-foreground">
            No runs yet — create an agent, build a workflow, then start a run.
          </p>
        )}
      </section>
    </PageShell>
  );
}
