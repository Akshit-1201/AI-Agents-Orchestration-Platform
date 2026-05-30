import { describe, expect, it } from "vitest";
import { isRunnable } from "./workflow";

describe("isRunnable", () => {
  it("is true when the workflow has an entry node", () => {
    expect(isRunnable({ entry_node_key: "n1" })).toBe(true);
  });

  it("is false when the entry node is null (empty / no entry set)", () => {
    expect(isRunnable({ entry_node_key: null })).toBe(false);
  });
});
