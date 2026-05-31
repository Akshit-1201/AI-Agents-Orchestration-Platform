"use client";

import * as React from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

export function Field({
  label,
  hint,
  error,
  children,
  className,
}: {
  label?: string;
  hint?: string;
  error?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("space-y-1.5", className)}>
      {label ? <label className="text-sm font-semibold">{label}</label> : null}
      {children}
      {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
      {error ? <p className="text-xs text-failed">{error}</p> : null}
    </div>
  );
}

export const NativeSelect = React.forwardRef<
  HTMLSelectElement,
  React.SelectHTMLAttributes<HTMLSelectElement>
>(function NativeSelect({ className, ...props }, ref) {
  return (
    <select
      ref={ref}
      className={cn(
        "h-9 w-full cursor-pointer rounded-lg border border-input bg-transparent px-3 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40 disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
});

/** Common model names suggested in the agent-config Model field (still free-typeable). */
export const MODEL_PRESETS = [
  "gpt-4.1-mini",
  "gpt-4.1-nano",
  "gpt-5-nano",
  "gpt-4o-mini",
  "qwen2.5",
  "qwen2.5:0.5b",
  "llama3.1",
  "llama3.2",
  "mistral",
  "mistral-nemo",
  "deepseek-r1",
] as const;

/**
 * Editable model combobox: a text input backed by a <datalist> of common presets, so the
 * user can pick a suggestion OR type any custom Ollama tag. Spreads props/ref so it drops
 * into react-hook-form's `register("model")` unchanged.
 */
export const ModelSelect = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(function ModelSelect({ className, ...props }, ref) {
  const listId = React.useId();
  return (
    <>
      <input
        ref={ref}
        list={listId}
        autoComplete="off"
        className={cn(
          "h-9 w-full rounded-lg border border-input bg-transparent px-3 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40",
          className,
        )}
        {...props}
      />
      <datalist id={listId}>
        {MODEL_PRESETS.map((m) => (
          <option key={m} value={m} />
        ))}
      </datalist>
    </>
  );
});

export function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-2 text-sm">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="size-4 cursor-pointer accent-primary"
      />
      {label}
    </label>
  );
}

/** Comma-separated text <-> string[] (for skills, blocked topics, allowed targets). */
export function TagInput({
  value,
  onChange,
  placeholder,
}: {
  value: string[];
  onChange: (v: string[]) => void;
  placeholder?: string;
}) {
  return (
    <input
      defaultValue={value.join(", ")}
      placeholder={placeholder}
      onBlur={(e) =>
        onChange(
          e.target.value
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
        )
      }
      className="h-9 w-full rounded-lg border border-input bg-transparent px-3 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
    />
  );
}

/** Edits a flat `Record<string,string>` (used for per-channel provider config). */
export function KeyValueEditor({
  value,
  onChange,
  addLabel = "Add field",
}: {
  value: Record<string, string>;
  onChange: (v: Record<string, string>) => void;
  addLabel?: string;
}) {
  const [rows, setRows] = React.useState<{ k: string; v: string }[]>(() =>
    Object.entries(value ?? {}).map(([k, v]) => ({ k, v })),
  );

  const sync = (next: { k: string; v: string }[]) => {
    setRows(next);
    const obj: Record<string, string> = {};
    for (const { k, v } of next) if (k.trim()) obj[k.trim()] = v;
    onChange(obj);
  };

  // Flag keys that won't survive saving to a Record: blank key with a value, or a duplicate
  // key (only the last wins). Without this the dropped row vanishes silently on save.
  const seen = new Set<string>();
  const problems = rows.map(({ k, v }) => {
    const key = k.trim();
    if (!key) return v.trim() ? "Missing key — this row won't be saved" : "";
    if (seen.has(key)) return "Duplicate key — only the last value is saved";
    seen.add(key);
    return "";
  });

  const inputCls =
    "h-8 rounded-lg border bg-transparent px-2.5 text-xs outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring/40";

  return (
    <div className="space-y-2">
      {rows.map((row, i) => (
        <div key={i} className="flex items-center gap-2">
          <input
            value={row.k}
            placeholder="key (e.g. chat_id)"
            title={problems[i] || undefined}
            aria-invalid={problems[i] ? true : undefined}
            onChange={(e) => sync(rows.map((r, idx) => (idx === i ? { ...r, k: e.target.value } : r)))}
            className={cn(
              inputCls,
              "w-40 font-mono",
              problems[i]
                ? "border-failed focus-visible:border-failed"
                : "border-input focus-visible:border-ring",
            )}
          />
          <input
            value={row.v}
            placeholder="value"
            onChange={(e) => sync(rows.map((r, idx) => (idx === i ? { ...r, v: e.target.value } : r)))}
            className={cn(inputCls, "flex-1 border-input focus-visible:border-ring")}
          />
          <button
            type="button"
            onClick={() => sync(rows.filter((_, idx) => idx !== i))}
            className="text-muted-foreground transition-colors hover:text-failed"
            aria-label="Remove field"
          >
            <X className="size-4" />
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={() => sync([...rows, { k: "", v: "" }])}
        className="text-xs text-muted-foreground transition-colors hover:text-foreground"
      >
        + {addLabel}
      </button>
    </div>
  );
}

export function SectionCard({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-border bg-card p-5">
      <div className="mb-4">
        <h3 className="text-sm font-semibold">{title}</h3>
        {description ? (
          <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {children}
    </section>
  );
}
