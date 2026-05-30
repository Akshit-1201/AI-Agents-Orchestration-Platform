import { describe, expect, it } from "vitest";
import type { Edge, Node } from "@xyflow/react";
import { buildWorkflowPayload } from "./payload";
import type { AgentNodeData } from "./agent-node";

const node = (
  key: string,
  agentId: number,
  x = 0,
  y = 0,
  nodeType: "agent" | "supervisor" = "agent",
): Node<AgentNodeData> => ({
  id: key,
  type: "agent",
  position: { x, y },
  data: { agentId, name: "A", role: "r", model: "m", nodeType, isEntry: false },
});

const edge = (s: string, t: string, condition: string | null = null): Edge => ({
  id: `${s}->${t}`,
  source: s,
  target: t,
  data: { condition },
});

describe("buildWorkflowPayload", () => {
  it("maps nodes/edges into the PUT payload by node_key, rounding positions", () => {
    const payload = buildWorkflowPayload(
      "WF",
      "n1",
      [node("n1", 5, 12.4, 8.6), node("n2", 7, 200, 0, "supervisor")],
      [edge("n1", "n2", "needs research")],
    );
    expect(payload.name).toBe("WF");
    expect(payload.entry_node_key).toBe("n1");
    expect(payload.nodes).toEqual([
      { agent_id: 5, node_key: "n1", node_type: "agent", position_x: 12, position_y: 9, label: null },
      { agent_id: 7, node_key: "n2", node_type: "supervisor", position_x: 200, position_y: 0, label: null },
    ]);
    expect(payload.edges).toEqual([
      { source_node_key: "n1", target_node_key: "n2", condition: "needs research" },
    ]);
  });

  it("defaults a missing edge condition to null", () => {
    const payload = buildWorkflowPayload("WF", "n1", [node("n1", 1)], [edge("n1", "n1")]);
    expect(payload.edges[0].condition).toBeNull();
  });

  it("produces a stable string for dirty-tracking (equal graphs match, changed graphs differ)", () => {
    const a = JSON.stringify(buildWorkflowPayload("WF", "n1", [node("n1", 1, 10, 10)], []));
    const b = JSON.stringify(buildWorkflowPayload("WF", "n1", [node("n1", 1, 10, 10)], []));
    const c = JSON.stringify(buildWorkflowPayload("WF", "n1", [node("n1", 1, 11, 10)], []));
    expect(a).toBe(b);
    expect(a).not.toBe(c);
  });
});
