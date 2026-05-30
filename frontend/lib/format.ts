export const fmtTokens = (n: number | null | undefined) =>
  (n ?? 0).toLocaleString();

export const fmtCost = (n: number | null | undefined) =>
  `$${(n ?? 0).toFixed(4)}`;

// Backend timestamps are UTC, but SQLite drops the tzinfo so the API sends a tz-less ISO
// string (e.g. "2026-05-30T12:00:00"). The browser would parse that as LOCAL time, skewing
// every "x ago" by the viewer's offset. Treat a tz-less string as UTC.
const TZ_RE = /[zZ]|[+-]\d\d:?\d\d$/;
export const parseApiDate = (iso: string): Date =>
  new Date(TZ_RE.test(iso) ? iso : `${iso}Z`);

export const fmtDateTime = (iso?: string | null) =>
  iso ? parseApiDate(iso).toLocaleString() : "—";

export function fmtRelative(iso?: string | null): string {
  if (!iso) return "—";
  const diff = Date.now() - parseApiDate(iso).getTime();
  const s = Math.round(diff / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.round(h / 24)}d ago`;
}
