"use client";

import "@xyflow/react/dist/style.css";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import {
  addEdge,
  Background,
  BackgroundVariant,
  Controls,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Connection,
  type Edge,
  type Node,
} from "@xyflow/react";
import { AlertTriangle, Bot, Flag, Play, Save, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/common/form";
import { AgentNode, type AgentNodeData } from "@/components/workflow/agent-node";
import { buildWorkflowPayload } from "@/components/workflow/payload";
import { useAgents, useUpdateWorkflow } from "@/lib/queries";
import type { WorkflowDetail } from "@/lib/types";

const nodeTypes = { agent: AgentNode };

export function FlowCanvas({ workflow }: { workflow: WorkflowDetail }) {
  const router = useRouter();
  const { resolvedTheme } = useTheme();
  const { data: agents } = useAgents();
  const agentsById = useMemo(
    () => new Map((agents ?? []).map((a) => [a.id, a])),
    [agents],
  );
  const update = useUpdateWorkflow(workflow.id);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node<AgentNodeData>>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [name, setName] = useState(workflow.name);
  const [entryKey, setEntryKey] = useState<string | null>(workflow.entry_node_key);
  const [selNode, setSelNode] = useState<string | null>(null);
  const [selEdge, setSelEdge] = useState<string | null>(null);
  const initialized = useRef(false);
  // JSON snapshot of the last-persisted graph; null until the canvas initializes.
  const savedRef = useRef<string | null>(null);

  // Build the graph once agents are available (so node labels resolve).
  useEffect(() => {
    if (initialized.current || !agents) return;
    initialized.current = true;
    const initNodes: Node<AgentNodeData>[] = workflow.nodes.map((n) => {
      const a = agentsById.get(n.agent_id);
      return {
        id: n.node_key,
        type: "agent",
        position: { x: n.position_x, y: n.position_y },
        data: {
          agentId: n.agent_id,
          name: a?.name ?? `#${n.agent_id}`,
          role: a?.role ?? "",
          model: a?.model ?? "",
          nodeType: n.node_type,
          isEntry: n.node_key === workflow.entry_node_key,
        },
      };
    });
    const initEdges: Edge[] = workflow.edges.map((e) => ({
      id: `${e.source_node_key}->${e.target_node_key}`,
      source: e.source_node_key,
      target: e.target_node_key,
      label: e.condition ?? undefined,
      data: { condition: e.condition ?? null },
    }));
    setNodes(initNodes);
    setEdges(initEdges);
    // Baseline for dirty-tracking (setting a ref in an effect is fine).
    savedRef.current = JSON.stringify(
      buildWorkflowPayload(workflow.name, workflow.entry_node_key, initNodes, initEdges),
    );
  }, [agents, agentsById, workflow, setNodes, setEdges]);

  // Keep the entry flag in sync.
  useEffect(() => {
    setNodes((nds) =>
      nds.map((n) => ({ ...n, data: { ...n.data, isEntry: n.id === entryKey } })),
    );
  }, [entryKey, setNodes]);

  const nextNodeKey = useCallback(() => {
    const used = nodes
      .map((n) => Number(/^n(\d+)$/.exec(n.id)?.[1]))
      .filter((x) => Number.isFinite(x));
    return `n${(used.length ? Math.max(...used) : 0) + 1}`;
  }, [nodes]);

  const addAgentNode = useCallback(
    (agentId: number) => {
      const a = agentsById.get(agentId);
      if (!a) return;
      const key = nextNodeKey();
      setNodes((nds) => [
        ...nds,
        {
          id: key,
          type: "agent",
          position: { x: 120 + ((nds.length * 40) % 280), y: 90 + ((nds.length * 60) % 220) },
          data: { agentId, name: a.name, role: a.role, model: a.model, nodeType: "agent", isEntry: false },
        },
      ]);
      if (!entryKey) setEntryKey(key);
    },
    [agentsById, nextNodeKey, setNodes, entryKey],
  );

  const onConnect = useCallback(
    (c: Connection) => {
      if (!c.source || !c.target) return;
      setEdges((eds) =>
        addEdge(
          { id: `${c.source}->${c.target}`, source: c.source, target: c.target, data: { condition: null } },
          eds,
        ),
      );
    },
    [setEdges],
  );

  const removeNode = useCallback(
    (id: string) => {
      setNodes((nds) => nds.filter((n) => n.id !== id));
      setEdges((eds) => eds.filter((e) => e.source !== id && e.target !== id));
      setSelNode(null);
      setEntryKey((k) => (k === id ? null : k));
    },
    [setNodes, setEdges],
  );

  const setNodeType = (id: string, t: "agent" | "supervisor") =>
    setNodes((nds) =>
      nds.map((n) => (n.id === id ? { ...n, data: { ...n.data, nodeType: t } } : n)),
    );

  const setEdgeCondition = (id: string, value: string) =>
    setEdges((eds) =>
      eds.map((e) =>
        e.id === id
          ? { ...e, label: value || undefined, data: { ...e.data, condition: value || null } }
          : e,
      ),
    );

  const payload = useMemo(
    () => buildWorkflowPayload(name, entryKey, nodes, edges),
    [name, entryKey, nodes, edges],
  );
  // A graph with nodes but no entry node can't be saved or run.
  const invalid = nodes.length > 0 && !entryKey;

  const persist = async (): Promise<boolean> => {
    try {
      await update.mutateAsync(payload);
      savedRef.current = JSON.stringify(payload);
      return true;
    } catch {
      return false; // useUpdateWorkflow surfaces the error via toast
    }
  };

  const save = () => {
    void persist();
  };

  // #3: never run a stale graph. Read the saved snapshot here (event handler, not
  // render) — if the current graph differs, save it before navigating to /runs/new.
  const runWorkflow = async () => {
    const dirty = savedRef.current !== null && JSON.stringify(payload) !== savedRef.current;
    if (dirty && !(await persist())) return;
    router.push(`/runs/new?workflow=${workflow.id}`);
  };

  const selectedNode = nodes.find((n) => n.id === selNode) ?? null;
  const selectedEdge = edges.find((e) => e.id === selEdge) ?? null;

  return (
    <div className="flex h-screen flex-col">
      {/* Toolbar */}
      <div className="flex h-14 shrink-0 items-center gap-3 border-b border-border px-4">
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="h-9 max-w-xs font-medium"
        />
        <span className="text-xs text-muted-foreground">
          {nodes.length} nodes · {edges.length} edges
        </span>
        {invalid ? (
          <span className="flex items-center gap-1 text-xs text-pending">
            <AlertTriangle className="size-3.5" /> Set an entry node to save or run
          </span>
        ) : null}
        <div className="ml-auto flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={save}
            disabled={update.isPending || invalid}
          >
            <Save className="size-4" /> {update.isPending ? "Saving…" : "Save"}
          </Button>
          <Button size="sm" onClick={runWorkflow} disabled={update.isPending || invalid}>
            <Play className="size-4" /> Run
          </Button>
        </div>
      </div>

      <div className="flex min-h-0 flex-1">
        {/* Palette */}
        <aside className="w-60 shrink-0 overflow-y-auto border-r border-border p-3 scrollbar-thin">
          <p className="px-1 pb-2 text-xs font-medium text-muted-foreground">
            Agents — click to add
          </p>
          <div className="space-y-1.5">
            {(agents ?? []).map((a) => (
              <button
                key={a.id}
                onClick={() => addAgentNode(a.id)}
                className="flex w-full items-center gap-2 rounded-md border border-border px-2.5 py-2 text-left text-sm transition-colors hover:bg-accent"
              >
                <Bot className="size-4 shrink-0 text-muted-foreground" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate">{a.name}</span>
                  <span className="block truncate text-[11px] text-muted-foreground">{a.role}</span>
                </span>
              </button>
            ))}
            {!agents?.length ? (
              <p className="px-1 text-xs text-muted-foreground">No agents yet.</p>
            ) : null}
          </div>
        </aside>

        {/* Canvas */}
        <div className="relative min-w-0 flex-1">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            nodeTypes={nodeTypes}
            onNodeClick={(_, n) => {
              setSelNode(n.id);
              setSelEdge(null);
            }}
            onEdgeClick={(_, e) => {
              setSelEdge(e.id);
              setSelNode(null);
            }}
            onPaneClick={() => {
              setSelNode(null);
              setSelEdge(null);
            }}
            fitView
            colorMode={resolvedTheme === "dark" ? "dark" : "light"}
            proOptions={{ hideAttribution: true }}
            defaultEdgeOptions={{ style: { stroke: "var(--color-muted-foreground)" } }}
          >
            <Background variant={BackgroundVariant.Dots} gap={18} size={1} color="var(--color-border)" />
            <Controls className="!rounded-lg !border !border-border !bg-card" />
          </ReactFlow>
        </div>

        {/* Inspector */}
        <aside className="w-72 shrink-0 overflow-y-auto border-l border-border p-4 scrollbar-thin">
          {selectedNode ? (
            <div className="space-y-4">
              <div>
                <p className="text-sm font-semibold">{selectedNode.data.name}</p>
                <p className="font-mono text-xs text-muted-foreground">{selectedNode.id}</p>
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-medium">Node type</label>
                <NativeSelect
                  value={selectedNode.data.nodeType}
                  onChange={(e) => setNodeType(selectedNode.id, e.target.value as "agent" | "supervisor")}
                >
                  <option value="agent">agent</option>
                  <option value="supervisor">supervisor</option>
                </NativeSelect>
              </div>
              <Button
                variant={entryKey === selectedNode.id ? "secondary" : "outline"}
                size="sm"
                className="w-full"
                onClick={() => setEntryKey(selectedNode.id)}
              >
                <Flag className="size-4" />
                {entryKey === selectedNode.id ? "Entry node" : "Set as entry"}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="w-full text-failed hover:text-failed"
                onClick={() => removeNode(selectedNode.id)}
              >
                <Trash2 className="size-4" /> Remove node
              </Button>
            </div>
          ) : selectedEdge ? (
            <div className="space-y-4">
              <p className="font-mono text-xs text-muted-foreground">
                {selectedEdge.source} → {selectedEdge.target}
              </p>
              <div className="space-y-1.5">
                <label className="text-xs font-medium">Condition</label>
                <Input
                  key={selectedEdge.id}
                  value={(selectedEdge.data?.condition as string) ?? ""}
                  placeholder="e.g. needs research"
                  onChange={(e) => setEdgeCondition(selectedEdge.id, e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  Conditioned out-edges are routed by an LLM at run time.
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="w-full text-failed hover:text-failed"
                onClick={() => {
                  setEdges((eds) => eds.filter((x) => x.id !== selectedEdge.id));
                  setSelEdge(null);
                }}
              >
                <Trash2 className="size-4" /> Remove edge
              </Button>
            </div>
          ) : (
            <div className="text-sm text-muted-foreground">
              <p className="font-medium text-foreground">Inspector</p>
              <p className="mt-2 text-xs leading-relaxed">
                Click an agent to add it. Drag from a node&apos;s right handle to another
                node&apos;s left handle to connect. Select a node or edge to edit it. Mark one
                node as the entry, then Save.
              </p>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
