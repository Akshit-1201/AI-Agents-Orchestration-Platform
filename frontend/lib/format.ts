export const fmtTokens = (n: number | null | undefined) =>
  (n ?? 0).toLocaleString();

export const fmtCost = (n: number | null | undefined) =>
  `$${(n ?? 0).toFixed(4)}`;

export const fmtDateTime = (iso?: string | null) =>
  iso ? new Date(iso).toLocaleString() : "—";

export function fmtRelative(iso?: string | null): string {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const s = Math.round(diff / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.round(h / 24)}d ago`;
}
