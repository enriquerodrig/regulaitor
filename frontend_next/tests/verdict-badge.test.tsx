import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { VerdictBadge } from "@/components/verdict-badge";

describe("VerdictBadge", () => {
  it("renders pass as Validado", () => {
    render(<VerdictBadge verdict="pass" />);
    expect(screen.getByText("Validado")).toBeInTheDocument();
  });

  it("renders block as Bloqueado", () => {
    render(<VerdictBadge verdict="block" />);
    expect(screen.getByText("Bloqueado")).toBeInTheDocument();
  });

  it("renders requires_human_review as a human-review notice", () => {
    render(<VerdictBadge verdict="requires_human_review" />);
    expect(screen.getByText("Requiere revisión humana")).toBeInTheDocument();
  });

  it("renders the verdict as plain text without a live-region role", () => {
    render(<VerdictBadge verdict="pass" />);
    expect(screen.queryByRole("status")).toBeNull();
    expect(screen.getByText("Validado")).toBeInTheDocument();
  });
});
