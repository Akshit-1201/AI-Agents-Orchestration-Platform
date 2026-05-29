"use client";

import { useRouter } from "next/navigation";
import { AgentForm } from "@/components/agents/agent-form";
import { PageHeader, PageShell } from "@/components/common/page-shell";
import { useCreateAgent } from "@/lib/queries";

export default function NewAgentPage() {
  const router = useRouter();
  const create = useCreateAgent();

  return (
    <PageShell>
      <PageHeader title="New agent" description="Define how this agent behaves and operates." />
      <AgentForm
        submitLabel="Create agent"
        pending={create.isPending}
        onSubmit={(values) =>
          create.mutate(values, { onSuccess: () => router.push("/agents") })
        }
      />
    </PageShell>
  );
}
