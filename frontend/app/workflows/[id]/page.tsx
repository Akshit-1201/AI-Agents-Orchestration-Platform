"use client";

import { useParams } from "next/navigation";
import { Loader2 } from "lucide-react";
import { FlowCanvas } from "@/components/workflow/flow-canvas";
import { useWorkflow } from "@/lib/queries";

export default function WorkflowBuilderPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const { data: workflow, isLoading } = useWorkflow(id);

  if (isLoading || !workflow) {
    return (
      <div className="flex h-screen items-center justify-center text-muted-foreground">
        <Loader2 className="size-5 animate-spin" />
      </div>
    );
  }

  return <FlowCanvas workflow={workflow} />;
}
