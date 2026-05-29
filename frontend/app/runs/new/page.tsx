"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Field, NativeSelect } from "@/components/common/form";
import { PageHeader, PageShell } from "@/components/common/page-shell";
import { useCreateRun, useWorkflows } from "@/lib/queries";

function NewRunInner() {
  const router = useRouter();
  const params = useSearchParams();
  const { data: workflows } = useWorkflows();
  const create = useCreateRun();

  const [workflowId, setWorkflowId] = useState<string>(params.get("workflow") ?? "");
  const [input, setInput] = useState("");

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const id = Number(workflowId);
    if (!id || !input.trim()) return;
    create.mutate(
      { body: { workflow_id: id, input: input.trim() } },
      { onSuccess: (run) => router.push(`/runs/${run.id}`) },
    );
  };

  return (
    <PageShell className="max-w-xl">
      <PageHeader title="New run" description="Pick a workflow and give it a task." />
      <form className="space-y-4" onSubmit={submit}>
        <Field label="Workflow">
          <NativeSelect value={workflowId} onChange={(e) => setWorkflowId(e.target.value)}>
            <option value="">Select a workflow…</option>
            {(workflows ?? []).map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </NativeSelect>
        </Field>
        <Field label="Input" hint="The task for the entry agent.">
          <Textarea
            rows={5}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Research the latest on… and write a short summary."
            autoFocus
          />
        </Field>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={() => router.push("/runs")}>
            Cancel
          </Button>
          <Button type="submit" disabled={create.isPending || !workflowId || !input.trim()}>
            {create.isPending ? "Starting…" : "Start run"}
          </Button>
        </div>
      </form>
    </PageShell>
  );
}

export default function NewRunPage() {
  return (
    <Suspense fallback={null}>
      <NewRunInner />
    </Suspense>
  );
}
