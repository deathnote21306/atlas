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

  it("uses a coming_soon foreground that meets WCAG AA on the badge background", () => {
    // ink-500 (#6b7280) on #21262d is 3.15:1 — below the 4.5:1 AA needs for the
    // 10px text this badge renders. ink-400 (#9ca3af) is 5.99:1. coming_soon is
    // the default for every newly ingested country, so it is the one that must
    // not be the unreadable one.
    render(<CoverageBadge status="coming_soon" />);
    const badge = screen.getByText("Coming Soon");
    expect(badge.className).toContain("text-ink-400");
    expect(badge.className).not.toContain("text-ink-500");
  });
});
