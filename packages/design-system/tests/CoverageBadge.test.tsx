import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { CoverageBadge } from "../src/primitives/CoverageBadge";

describe("CoverageBadge", () => {
  it("renders the full label for each known status", () => {
    const cases: [string, string][] = [
      ["full", "Full Intelligence"],
      ["standard", "Standard Intelligence"],
      ["benchmark", "Benchmark Data"],
      ["coming_soon", "Coming Soon"],
    ];
    for (const [status, label] of cases) {
      const { unmount } = render(<CoverageBadge status={status} />);
      expect(screen.getByText(label)).toBeInTheDocument();
      unmount();
    }
  });

  it("falls back to Unknown for an unrecognised status instead of crashing", () => {
    render(<CoverageBadge status="legacy_value" />);
    expect(screen.getByText("Unknown")).toBeInTheDocument();
  });

  it("carries the label in its accessible name so colour is not the only signal", () => {
    render(<CoverageBadge status="benchmark" />);
    expect(screen.getByTitle("Benchmark Data")).toBeInTheDocument();
  });
});
