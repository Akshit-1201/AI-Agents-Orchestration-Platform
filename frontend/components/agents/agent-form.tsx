"use client";

import { useForm, useFieldArray } from "react-hook-form";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Field, NativeSelect, SectionCard, TagInput, Toggle } from "@/components/common/form";
import { TOOL_NAMES, type AgentCreate } from "@/lib/types";
import { cn } from "@/lib/utils";

const DEFAULTS: AgentCreate = {
  name: "",
  role: "",
  model: "gemini-2.5-flash",
  system_prompt: "",
  description: "",
  tools: [],
  skills: [],
  channels: [],
  schedules: [],
  memory: { enabled: false, type: "none", window: null, persist: false },
  interaction_rules: { can_delegate: true, allowed_targets: [], response_style: null },
  guardrails: { blocked_topics: [], allowed_tools_only: true, max_output_chars: null },
  limits: { max_steps: null, max_tokens: null, max_cost_usd: null, timeout_seconds: null },
};

const numOrNull = { setValueAs: (v: unknown) => (v === "" || v == null ? null : Number(v)) };

export function AgentForm({
  initial,
  submitLabel = "Save agent",
  pending,
  onSubmit,
}: {
  initial?: AgentCreate;
  submitLabel?: string;
  pending?: boolean;
  onSubmit: (values: AgentCreate) => void;
}) {
  const form = useForm<AgentCreate>({ defaultValues: initial ?? DEFAULTS });
  const { register, handleSubmit, watch, setValue, control, formState } = form;
  const errors = formState.errors;

  const channels = useFieldArray({ control, name: "channels" });
  const schedules = useFieldArray({ control, name: "schedules" });
  const tools = watch("tools");

  const toggleTool = (t: string) =>
    setValue(
      "tools",
      tools.includes(t) ? tools.filter((x) => x !== t) : [...tools, t],
      { shouldDirty: true },
    );

  return (
    <form
      onSubmit={handleSubmit((v) => onSubmit(v))}
      className="space-y-5"
    >
      <SectionCard title="General" description="Identity and the system prompt that defines this agent.">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Name" error={errors.name && "Required"}>
            <Input placeholder="Researcher" {...register("name", { required: true })} />
          </Field>
          <Field label="Role" error={errors.role && "Required"}>
            <Input placeholder="researcher" {...register("role", { required: true })} />
          </Field>
          <Field label="Model" error={errors.model && "Required"}>
            <Input placeholder="gemini-2.5-flash" {...register("model", { required: true })} />
          </Field>
          <Field label="Description" hint="Optional, shown in lists.">
            <Input placeholder="Finds and summarizes information" {...register("description")} />
          </Field>
        </div>
        <Field className="mt-4" label="System prompt" error={errors.system_prompt && "Required"}>
          <Textarea
            rows={5}
            placeholder="You are a meticulous research assistant..."
            {...register("system_prompt", { required: true })}
          />
        </Field>
      </SectionCard>

      <SectionCard title="Tools & skills" description="Tools must be in the backend registry; skills are free-form labels.">
        <Field label="Tools">
          <div className="flex flex-wrap gap-2">
            {TOOL_NAMES.map((t) => {
              const on = tools.includes(t);
              return (
                <button
                  key={t}
                  type="button"
                  onClick={() => toggleTool(t)}
                  className={cn(
                    "rounded-full border px-3 py-1 font-mono text-xs transition-colors",
                    on
                      ? "border-primary/40 bg-primary/15 text-primary"
                      : "border-border text-muted-foreground hover:bg-accent",
                  )}
                >
                  {t}
                </button>
              );
            })}
          </div>
        </Field>
        <Field className="mt-4" label="Skills" hint="Comma-separated.">
          <TagInput
            value={watch("skills")}
            onChange={(v) => setValue("skills", v, { shouldDirty: true })}
            placeholder="summarize, plan, critique"
          />
        </Field>
      </SectionCard>

      <div className="grid gap-5 lg:grid-cols-2">
        <SectionCard title="Memory" description="Conversation memory for this agent.">
          <div className="space-y-3">
            <Toggle
              checked={watch("memory.enabled")}
              onChange={(v) => setValue("memory.enabled", v)}
              label="Enable memory"
            />
            <div className="grid grid-cols-2 gap-3">
              <Field label="Type">
                <NativeSelect {...register("memory.type")}>
                  <option value="none">none</option>
                  <option value="buffer">buffer</option>
                  <option value="summary">summary</option>
                </NativeSelect>
              </Field>
              <Field label="Window">
                <Input type="number" placeholder="10" {...register("memory.window", numOrNull)} />
              </Field>
            </div>
            <Toggle
              checked={watch("memory.persist")}
              onChange={(v) => setValue("memory.persist", v)}
              label="Persist across runs"
            />
          </div>
        </SectionCard>

        <SectionCard title="Limits" description="Caps enforced by the runtime.">
          <div className="grid grid-cols-2 gap-3">
            <Field label="Max steps">
              <Input type="number" placeholder="12" {...register("limits.max_steps", numOrNull)} />
            </Field>
            <Field label="Max tokens">
              <Input type="number" placeholder="—" {...register("limits.max_tokens", numOrNull)} />
            </Field>
            <Field label="Max cost (USD)">
              <Input type="number" step="0.01" placeholder="—" {...register("limits.max_cost_usd", numOrNull)} />
            </Field>
            <Field label="Timeout (s)">
              <Input type="number" placeholder="—" {...register("limits.timeout_seconds", numOrNull)} />
            </Field>
          </div>
        </SectionCard>

        <SectionCard title="Guardrails" description="Light safety constraints.">
          <Field label="Blocked topics" hint="Comma-separated.">
            <TagInput
              value={watch("guardrails.blocked_topics")}
              onChange={(v) => setValue("guardrails.blocked_topics", v)}
              placeholder="nsfw, legal advice"
            />
          </Field>
          <div className="mt-3 space-y-3">
            <Toggle
              checked={watch("guardrails.allowed_tools_only")}
              onChange={(v) => setValue("guardrails.allowed_tools_only", v)}
              label="Only configured tools"
            />
            <Field label="Max output chars">
              <Input type="number" placeholder="—" {...register("guardrails.max_output_chars", numOrNull)} />
            </Field>
          </div>
        </SectionCard>

        <SectionCard title="Interaction rules" description="How this agent collaborates (used by supervisors).">
          <div className="space-y-3">
            <Toggle
              checked={watch("interaction_rules.can_delegate")}
              onChange={(v) => setValue("interaction_rules.can_delegate", v)}
              label="Can delegate to others"
            />
            <Field label="Allowed targets" hint="node_keys it may route to; comma-separated.">
              <TagInput
                value={watch("interaction_rules.allowed_targets")}
                onChange={(v) => setValue("interaction_rules.allowed_targets", v)}
                placeholder="n2, n3"
              />
            </Field>
            <Field label="Response style">
              <Input placeholder="concise" {...register("interaction_rules.response_style")} />
            </Field>
          </div>
        </SectionCard>
      </div>

      <SectionCard title="Channels" description="External messaging bindings (config wired in Phase 5).">
        <div className="space-y-3">
          {channels.fields.map((f, i) => (
            <div key={f.id} className="flex items-center gap-3">
              <NativeSelect className="max-w-40" {...register(`channels.${i}.provider`)}>
                <option value="telegram">telegram</option>
                <option value="slack">slack</option>
                <option value="whatsapp">whatsapp</option>
              </NativeSelect>
              <Toggle
                checked={watch(`channels.${i}.enabled`)}
                onChange={(v) => setValue(`channels.${i}.enabled`, v)}
                label="Enabled"
              />
              <Button type="button" variant="ghost" size="icon" onClick={() => channels.remove(i)}>
                <Trash2 className="size-4" />
              </Button>
            </div>
          ))}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => channels.append({ provider: "telegram", enabled: true, config: {} })}
          >
            <Plus className="size-4" /> Add channel
          </Button>
        </div>
      </SectionCard>

      <SectionCard title="Schedules" description="When the agent runs (scheduler arrives later).">
        <div className="space-y-3">
          {schedules.fields.map((f, i) => (
            <div key={f.id} className="flex items-center gap-3">
              <NativeSelect className="max-w-40" {...register(`schedules.${i}.type`)}>
                <option value="manual">manual</option>
                <option value="interval">interval</option>
                <option value="cron">cron</option>
              </NativeSelect>
              <Input
                className="font-mono"
                placeholder="0 9 * * *"
                {...register(`schedules.${i}.expr`)}
              />
              <Toggle
                checked={watch(`schedules.${i}.enabled`)}
                onChange={(v) => setValue(`schedules.${i}.enabled`, v)}
                label="On"
              />
              <Button type="button" variant="ghost" size="icon" onClick={() => schedules.remove(i)}>
                <Trash2 className="size-4" />
              </Button>
            </div>
          ))}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => schedules.append({ type: "manual", expr: "", enabled: false })}
          >
            <Plus className="size-4" /> Add schedule
          </Button>
        </div>
      </SectionCard>

      <div className="flex justify-end gap-2">
        <Button type="submit" disabled={pending}>
          {pending ? "Saving…" : submitLabel}
        </Button>
      </div>
    </form>
  );
}

export { DEFAULTS as emptyAgent };
