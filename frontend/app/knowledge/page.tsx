"use client";

import { useRef, useState } from "react";
import { FileText, Trash2, Upload } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader, PageShell } from "@/components/common/page-shell";
import { ConfirmButton } from "@/components/common/confirm-button";
import { useDeleteKnowledge, useKnowledge, useUploadKnowledge } from "@/lib/queries";
import { cn } from "@/lib/utils";

const ACCEPT = ".txt,.md,.pdf";

export default function KnowledgePage() {
  const { data: sources, isLoading } = useKnowledge();
  const upload = useUploadKnowledge();
  const del = useDeleteKnowledge();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const send = (files: FileList | null) => {
    const list = files ? Array.from(files) : [];
    if (list.length) upload.mutate(list);
  };

  return (
    <PageShell>
      <PageHeader
        title="Knowledge"
        description="Upload documents to the knowledge base. Agents with the knowledge_search tool can search them at run time."
      />

      {/* Upload area */}
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload documents"
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          send(e.dataTransfer.files);
        }}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border border-dashed px-6 py-12 text-center transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring",
          dragging ? "border-primary bg-primary/5" : "border-border hover:border-foreground/30",
        )}
      >
        <Upload className="size-7 text-muted-foreground" />
        <p className="text-sm font-semibold">
          {upload.isPending ? "Ingesting…" : "Drop files here, or click to choose"}
        </p>
        <p className="text-xs text-muted-foreground">.txt, .md, or .pdf · up to 10 MB each</p>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          multiple
          className="hidden"
          onChange={(e) => {
            send(e.target.files);
            e.target.value = ""; // allow re-selecting the same file
          }}
        />
      </div>

      {/* Existing documents */}
      <div className="space-y-2">
        <h2 className="text-sm font-semibold text-muted-foreground">In the knowledge base</h2>
        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-12 rounded-lg" />
            ))}
          </div>
        ) : !sources?.length ? (
          <p className="rounded-xl border border-dashed border-border py-10 text-center text-sm text-muted-foreground">
            No documents yet. Upload one above to get started.
          </p>
        ) : (
          <div className="overflow-hidden rounded-xl border border-border">
            {sources.map((s) => (
              <div
                key={s.source}
                className="flex items-center gap-3 border-b border-border bg-card px-4 py-3 text-sm last:border-0"
              >
                <FileText className="size-4 shrink-0 text-muted-foreground" />
                <span className="min-w-0 flex-1 truncate font-mono">{s.source}</span>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {s.chunks} chunk{s.chunks === 1 ? "" : "s"}
                </span>
                <ConfirmButton
                  variant="ghost"
                  size="icon-sm"
                  className="text-failed hover:text-failed"
                  confirmLabel="?"
                  onConfirm={() => del.mutate(s.source)}
                  aria-label={`Delete ${s.source}`}
                >
                  <Trash2 className="size-3.5" />
                </ConfirmButton>
              </div>
            ))}
          </div>
        )}
      </div>
    </PageShell>
  );
}
