"use client";

import { Handle, Position, type NodeProps } from "@xyflow/react";
import { Bot, Crown, Flag } from "lucide-react";
import { cn } from "@/lib/utils";

export interface AgentNodeData {
  agentId: number;
  name: string;
  role: string;
  model: string;
  nodeType: "agent" | "supervisor";
  isEntry: boolean;
  [key: string]: unknown;
}

export function AgentNode({ data, selected }: NodeProps) {
  const d = data as AgentNodeData;
  const supervisor = d.nodeType === "supervisor";
  return (
    <div
      className={cn(
        "w-52 rounded-xl border bg-card px-3 py-2.5 shadow-md transition-colors",
        selected ? "border-brand ring-2 ring-brand/30" : "border-border",
        supervisor && !selected && "border-brand/40",
      )}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!size-2.5 !border-2 !border-background !bg-muted-foreground"
      />
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "grid size-7 shrink-0 place-items-center rounded-md",
            supervisor ? "bg-brand/15 text-brand" : "bg-muted text-foreground",
          )}
        >
          {supervisor ? <Crown className="size-4" /> : <Bot className="size-4" />}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{d.name}</p>
          <p className="truncate text-[11px] text-muted-foreground">{d.role}</p>
        </div>
        {d.isEntry ? (
          <span title="Entry node">
            <Flag className="size-3.5 text-completed" />
          </span>
        ) : null}
      </div>
      <p className="mt-1.5 font-mono text-[10px] text-muted-foreground">{d.model}</p>
      <Handle
        type="source"
        position={Position.Right}
        className="!size-2.5 !border-2 !border-background !bg-muted-foreground"
      />
    </div>
  );
}
