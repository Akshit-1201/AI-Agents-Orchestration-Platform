"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Field, NativeSelect } from "@/components/common/form";
import { PageHeader, PageShell } from "@/components/common/page-shell";
import { useCreateChat, useWorkflows } from "@/lib/queries";
import { isRunnable } from "@/lib/workflow";

function NewChatInner() {
  const router = useRouter();
  const params = useSearchParams();
  const { data: workflows } = useWorkflows();
  const create = useCreateChat();

  const [workflowId, setWorkflowId] = useState<string>(params.get("workflow") ?? "");
  const selected = (workflows ?? []).find((w) => String(w.id) === workflowId);
  const runnable = selected ? isRunnable(selected) : false;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const id = Number(workflowId);
    if (!id || !runnable) return;
    create.mutate(
      { workflow_id: id },
      { onSuccess: (chat) => router.push(`/chats/${chat.id}`) },
    );
  };

  return (
    <PageShell className="max-w-xl">
      <PageHeader title="New chat" description="Pick a workflow to chat with." />
      <form className="space-y-4" onSubmit={submit}>
        <Field label="Workflow">
          <NativeSelect value={workflowId} onChange={(e) => setWorkflowId(e.target.value)}>
            <option value="">Select a workflow…</option>
            {(workflows ?? []).map((w) => (
              <option key={w.id} value={w.id} disabled={!isRunnable(w)}>
                {w.name}
                {isRunnable(w) ? "" : " — no entry node"}
              </option>
            ))}
          </NativeSelect>
          {workflowId && !runnable ? (
            <p className="mt-1.5 text-xs text-pending">
              This workflow has no entry node — set one in the builder before chatting.
            </p>
          ) : null}
        </Field>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={() => router.push("/chats")}>
            Cancel
          </Button>
          <Button type="submit" disabled={create.isPending || !workflowId || !runnable}>
            {create.isPending ? "Creating…" : "Start chat"}
          </Button>
        </div>
      </form>
    </PageShell>
  );
}

export default function NewChatPage() {
  return (
    <Suspense fallback={null}>
      <NewChatInner />
    </Suspense>
  );
}
