import type { Edge, Node } from "@xyflow/react";
import type { EdgeInput, NodeInput, WorkflowUpdate } from "@/lib/types";
import type { AgentNodeData } from "./agent-node";

/** A full graph-replacement payload (always carries nodes + edges). */
export type WorkflowSavePayload = Omit<WorkflowUpdate, "nodes" | "edges"> & {
  nodes: NodeInput[];
  edges: EdgeInput[];
};

/**
 * Maps the React Flow canvas state into the `PUT /workflows/{id}` payload.
 * Edges reference nodes by `node_key` (the client-side node id). Pure + exported
 * so the canvas, its dirty-check, and tests all share one source of truth.
 */
export function buildWorkflowPayload(
  name: string,
  entryKey: string | null,
  nodes: Node<AgentNodeData>[],
  edges: Edge[],
): WorkflowSavePayload {
  return {
    name,
    entry_node_key: entryKey,
    nodes: nodes.map((n) => ({
      agent_id: n.data.agentId,
      node_key: n.id,
      node_type: n.data.nodeType,
      position_x: Math.round(n.position.x),
      position_y: Math.round(n.position.y),
      label: null,
    })),
    edges: edges.map((e) => ({
      source_node_key: e.source,
      target_node_key: e.target,
      condition: (e.data?.condition as string | null) ?? null,
    })),
  };
}
