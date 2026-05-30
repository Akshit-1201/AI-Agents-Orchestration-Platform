"use client";

import { Controller, useFieldArray, useForm, useWatch } from "react-hook-form";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Field, KeyValueEditor, ModelSelect, NativeSelect, SectionCard, TagInput, Toggle } from "@/components/common/form";
import { TOOL_NAMES, type AgentCreate } from "@/lib/types";
import { cn } from "@/lib/utils";

const DEFAULTS: AgentCreate = {
  name: "",
  role: "",
  model: "gpt-4.1-mini",
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
  const { register, handleSubmit, setValue, control, formState } = form;
  const errors = formState.errors;

  const channels = useFieldArray({ control, name: "channels" });
  const schedules = useFieldArray({ control, name: "schedules" });
  const tools = useWatch({ control, name: "tools" }) ?? [];

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
          <Field
            label="Model"
            error={errors.model && "Required"}
            hint="gpt-*/o* models run via OpenAI (cloud, tool-capable); any other name runs on local Ollama (must be pulled). For tools, prefer an OpenAI model (e.g. gpt-4.1-mini) or a tool-capable local model (qwen2.5, llama3.1) — tiny/reasoning models (qwen2.5:0.5b, deepseek-r1) can't reliably call tools."
          >
            <ModelSelect placeholder="gpt-4.1-mini" {...register("model", { required: true })} />
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
          <Controller
            control={control}
            name="skills"
            render={({ field }) => (
              <TagInput
                value={field.value}
                onChange={field.onChange}
                placeholder="summarize, plan, critique"
              />
            )}
          />
        </Field>
      </SectionCard>

      <div className="grid gap-5 lg:grid-cols-2">
        <SectionCard title="Memory" description="Conversation memory for this agent.">
          <div className="space-y-3">
            <Controller
              control={control}
              name="memory.enabled"
              render={({ field }) => (
                <Toggle checked={field.value} onChange={field.onChange} label="Enable memory" />
              )}
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
            <Controller
              control={control}
              name="memory.persist"
              render={({ field }) => (
                <Toggle checked={field.value} onChange={field.onChange} label="Persist across runs" />
              )}
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
            <Controller
              control={control}
              name="guardrails.blocked_topics"
              render={({ field }) => (
                <TagInput
                  value={field.value}
                  onChange={field.onChange}
                  placeholder="nsfw, legal advice"
                />
              )}
            />
          </Field>
          <div className="mt-3 space-y-3">
            <Controller
              control={control}
              name="guardrails.allowed_tools_only"
              render={({ field }) => (
                <Toggle checked={field.value} onChange={field.onChange} label="Only configured tools" />
              )}
            />
            <Field label="Max output chars">
              <Input type="number" placeholder="—" {...register("guardrails.max_output_chars", numOrNull)} />
            </Field>
          </div>
        </SectionCard>

        <SectionCard title="Interaction rules" description="How this agent collaborates (used by supervisors).">
          <div className="space-y-3">
            <Controller
              control={control}
              name="interaction_rules.can_delegate"
              render={({ field }) => (
                <Toggle checked={field.value} onChange={field.onChange} label="Can delegate to others" />
              )}
            />
            <Field label="Allowed targets" hint="node_keys it may route to; comma-separated.">
              <Controller
                control={control}
                name="interaction_rules.allowed_targets"
                render={({ field }) => (
                  <TagInput value={field.value} onChange={field.onChange} placeholder="n2, n3" />
                )}
              />
            </Field>
            <Field label="Response style">
              <Input placeholder="concise" {...register("interaction_rules.response_style")} />
            </Field>
          </div>
        </SectionCard>
      </div>

      <SectionCard title="Channels" description="External messaging bindings and their provider config (key/value).">
        <div className="space-y-3">
          {channels.fields.map((f, i) => (
            <div key={f.id} className="space-y-3 rounded-lg border border-border p-3">
              <div className="flex items-center gap-3">
                <NativeSelect className="max-w-40" {...register(`channels.${i}.provider`)}>
                  <option value="telegram">telegram</option>
                  <option value="slack">slack</option>
                  <option value="whatsapp">whatsapp</option>
                </NativeSelect>
                <Controller
                  control={control}
                  name={`channels.${i}.enabled`}
                  render={({ field }) => (
                    <Toggle checked={field.value} onChange={field.onChange} label="Enabled" />
                  )}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="ml-auto"
                  onClick={() => channels.remove(i)}
                >
                  <Trash2 className="size-4" />
                </Button>
              </div>
              <Field label="Config" hint="Provider settings as key/value (e.g. chat_id, webhook_url).">
                <Controller
                  control={control}
                  name={`channels.${i}.config`}
                  render={({ field }) => (
                    <KeyValueEditor value={field.value ?? {}} onChange={field.onChange} />
                  )}
                />
              </Field>
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
              <Controller
                control={control}
                name={`schedules.${i}.enabled`}
                render={({ field }) => (
                  <Toggle checked={field.value} onChange={field.onChange} label="On" />
                )}
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
