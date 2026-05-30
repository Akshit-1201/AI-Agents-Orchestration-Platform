import type { Workflow } from "./types";

/**
 * A workflow can be run only if it has an entry node set. The list endpoint
 * doesn't return node counts, but an empty workflow also has a null entry, so
 * `entry_node_key` is a reliable runnable signal.
 */
export function isRunnable(workflow: Pick<Workflow, "entry_node_key">): boolean {
  return workflow.entry_node_key != null;
}
