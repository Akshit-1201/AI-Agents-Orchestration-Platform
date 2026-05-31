import type { LucideIcon } from "lucide-react";
import { Ban, CheckCircle2, Clock, Loader2, XCircle } from "lucide-react";
import type { RunStatus } from "./types";

// Apple system colors (legible on both white cards and near-black tiles).
export const STATUS_META: Record<
  RunStatus,
  { label: string; color: string; className: string; icon: LucideIcon }
> = {
  pending: { label: "Pending", color: "#ff9500", className: "border-pending/30 bg-pending/10 text-pending", icon: Clock },
  running: { label: "Running", color: "#0a84ff", className: "border-running/30 bg-running/10 text-running", icon: Loader2 },
  completed: { label: "Completed", color: "#34c759", className: "border-completed/30 bg-completed/10 text-completed", icon: CheckCircle2 },
  failed: { label: "Failed", color: "#ff3b30", className: "border-failed/30 bg-failed/10 text-failed", icon: XCircle },
  cancelled: { label: "Cancelled", color: "#8e8e93", className: "border-cancelled/30 bg-cancelled/10 text-cancelled", icon: Ban },
};

// Message role -> tint (used in the live monitor timeline). Kept as hex so the
// timeline can derive a 10%-alpha background via `${color}1a`.
export const ROLE_COLOR: Record<string, string> = {
  user: "#8e8e93",
  assistant: "#0a84ff",
  tool: "#34c759",
  system: "#af52de",
};

// Recharts series colors (token/cost), aligned to the Apple system palette.
export const CHART_COLORS = ["#0a84ff", "#34c759", "#ff9500", "#5ac8fa", "#ff3b30"];
