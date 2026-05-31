import { cn } from "@/lib/utils";
import { STATUS_META } from "@/lib/status";
import type { RunStatus } from "@/lib/types";

export function StatusBadge({
  status,
  className,
}: {
  status: RunStatus;
  className?: string;
}) {
  const meta = STATUS_META[status] ?? STATUS_META.pending;
  const Icon = meta.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold",
        meta.className,
        className,
      )}
    >
      <Icon className={cn("size-3.5", status === "running" && "animate-spin")} />
      {meta.label}
    </span>
  );
}
