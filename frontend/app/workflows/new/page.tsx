"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Field } from "@/components/common/form";
import { PageHeader, PageShell } from "@/components/common/page-shell";
import { useCreateWorkflow } from "@/lib/queries";

export default function NewWorkflowPage() {
  const router = useRouter();
  const create = useCreateWorkflow();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  return (
    <PageShell className="max-w-xl">
      <PageHeader title="New workflow" description="Name it, then design the graph." />
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          if (!name.trim()) return;
          create.mutate(
            { name: name.trim(), description: description.trim() || null, nodes: [], edges: [] },
            { onSuccess: (wf) => router.push(`/workflows/${wf.id}`) },
          );
        }}
      >
        <Field label="Name">
          <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Research → Write" autoFocus />
        </Field>
        <Field label="Description" hint="Optional.">
          <Textarea
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="A supervisor routes a researcher and a writer."
          />
        </Field>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={() => router.push("/workflows")}>
            Cancel
          </Button>
          <Button type="submit" disabled={create.isPending || !name.trim()}>
            {create.isPending ? "Creating…" : "Create & open builder"}
          </Button>
        </div>
      </form>
    </PageShell>
  );
}
