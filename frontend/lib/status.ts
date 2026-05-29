import type { LucideIcon } from "lucide-react";
import { Ban, CheckCircle2, Clock, Loader2, XCircle } from "lucide-react";
import type { RunStatus } from "./types";

export const STATUS_META: Record<
  RunStatus,
  { label: string; color: string; className: string; icon: LucideIcon }
> = {
  pending: { label: "Pending", color: "#f59e0b", className: "border-pending/30 bg-pending/10 text-pending", icon: Clock },
  running: { label: "Running", color: "#6366f1", className: "border-running/30 bg-running/10 text-running", icon: Loader2 },
  completed: { label: "Completed", color: "#22c55e", className: "border-completed/30 bg-completed/10 text-completed", icon: CheckCircle2 },
  failed: { label: "Failed", color: "#ef4444", className: "border-failed/30 bg-failed/10 text-failed", icon: XCircle },
  cancelled: { label: "Cancelled", color: "#64748b", className: "border-cancelled/30 bg-cancelled/10 text-cancelled", icon: Ban },
};

// Message role -> tint (used in the live monitor timeline).
export const ROLE_COLOR: Record<string, string> = {
  user: "#94a3b8",
  assistant: "#818cf8",
  tool: "#2dd4bf",
  system: "#64748b",
};

// Recharts series colors (token/cost), aligned to the design system.
export const CHART_COLORS = ["#6366f1", "#22c55e", "#f59e0b", "#2dd4bf", "#ef4444"];
