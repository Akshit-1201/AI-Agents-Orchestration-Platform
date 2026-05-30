"use client";

import { useMemo } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { MessageSquare, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ConfirmButton } from "@/components/common/confirm-button";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader, PageShell } from "@/components/common/page-shell";
import { fmtRelative } from "@/lib/format";
import { useChats, useDeleteChat, useWorkflows } from "@/lib/queries";

export default function ChatsPage() {
  const router = useRouter();
  const { data: chats, isLoading } = useChats();
  const { data: workflows } = useWorkflows();
  const del = useDeleteChat();
  const wfName = useMemo(
    () => new Map((workflows ?? []).map((w) => [w.id, w.name])),
    [workflows],
  );

  return (
    <PageShell>
      <PageHeader
        title="Chats"
        description="Hold a conversation with a workflow — each chat keeps its own memory."
        action={
          <Button onClick={() => router.push("/chats/new")}>
            <Plus className="size-4" /> New chat
          </Button>
        }
      />

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-16 rounded-xl" />
          ))}
        </div>
      ) : !chats?.length ? (
        <div className="rounded-xl border border-dashed border-border py-16 text-center">
          <MessageSquare className="mx-auto size-8 text-muted-foreground/60" />
          <p className="mt-3 text-sm text-muted-foreground">No chats yet.</p>
          <Button className="mt-4" onClick={() => router.push("/chats/new")}>
            <Plus className="size-4" /> Start a chat
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          {chats.map((c, i) => {
            const open = () => router.push(`/chats/${c.id}`);
            return (
              <motion.div
                key={c.id}
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
                className="group flex w-full cursor-pointer items-center gap-4 rounded-xl border border-border bg-card/60 p-4 text-left transition-colors hover:border-border/80 hover:bg-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-brand/15 text-brand">
                  <MessageSquare className="size-5" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{c.title}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {wfName.get(c.workflow_id) ?? `Workflow #${c.workflow_id}`} ·{" "}
                    {fmtRelative(c.updated_at)}
                  </p>
                </div>
                <ConfirmButton
                  variant="ghost"
                  size="sm"
                  className="text-failed opacity-0 transition-opacity group-hover:opacity-100 hover:text-failed"
                  onConfirm={() => del.mutate(c.id)}
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
