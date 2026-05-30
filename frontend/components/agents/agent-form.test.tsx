import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AgentForm } from "./agent-form";

describe("AgentForm", () => {
  it("submits the AgentCreate shape with edits + default config blocks", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<AgentForm onSubmit={onSubmit} />);

    await user.type(screen.getByPlaceholderText("Researcher"), "Planner");
    await user.type(screen.getByPlaceholderText("researcher"), "planner");
    await user.type(
      screen.getByPlaceholderText(/meticulous research assistant/i),
      "Plan the work.",
    );
    await user.click(screen.getByRole("button", { name: "calculator" }));
    await user.click(screen.getByRole("button", { name: /save agent/i }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));

    const values = onSubmit.mock.calls[0][0];
    expect(values).toMatchObject({
      name: "Planner",
      role: "planner",
      model: "gpt-4.1-mini",
      system_prompt: "Plan the work.",
      tools: ["calculator"],
    });
    expect(values.memory).toEqual({ enabled: false, type: "none", window: null, persist: false });
    expect(values.limits).toEqual({
      max_steps: null,
      max_tokens: null,
      max_cost_usd: null,
      timeout_seconds: null,
    });
    expect(Array.isArray(values.channels)).toBe(true);
  });

  it("blocks submit when required fields are empty", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<AgentForm onSubmit={onSubmit} />);

    await user.click(screen.getByRole("button", { name: /save agent/i }));

    // RHF required validation should prevent the submit handler from firing.
    await new Promise((r) => setTimeout(r, 50));
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
