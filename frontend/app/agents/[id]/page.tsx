"use client";

import { useParams, useRouter } from "next/navigation";
import { AgentForm } from "@/components/agents/agent-form";
import { PageHeader, PageShell } from "@/components/common/page-shell";
import { Skeleton } from "@/components/ui/skeleton";
import { useAgent, useUpdateAgent } from "@/lib/queries";
import type { AgentCreate } from "@/lib/types";

export default function EditAgentPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const router = useRouter();
  const { data: agent, isLoading } = useAgent(id);
  const update = useUpdateAgent(id);

  return (
    <PageShell>
      <PageHeader title="Edit agent" description={agent?.name} />
      {isLoading || !agent ? (
        <Skeleton className="h-96 w-full rounded-xl" />
      ) : (
        <AgentForm
          initial={toCreate(agent)}
          submitLabel="Save changes"
          pending={update.isPending}
          onSubmit={(values) =>
            update.mutate(values, { onSuccess: () => router.push("/agents") })
          }
        />
      )}
    </PageShell>
  );
}

function toCreate(agent: AgentCreate & { id: number; created_at: string }): AgentCreate {
  // Drop the server-only fields; the form edits the AgentCreate shape.
  const { id, created_at, ...rest } = agent;
  return rest;
}
