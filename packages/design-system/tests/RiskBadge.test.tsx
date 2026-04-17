import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { RiskBadge } from "../src/primitives/RiskBadge";

describe("RiskBadge", () => {
  it("renders LOW for score <= 25", () => {
    render(<RiskBadge score={20} />);
    expect(screen.getByText("LOW")).toBeInTheDocument();
  });

  it("renders CRITICAL for score > 70", () => {
    render(<RiskBadge score={75} />);
    expect(screen.getByText("CRITICAL")).toBeInTheDocument();
  });

  it("renders ELEVATED for score 41-55", () => {
    render(<RiskBadge score={50} />);
    expect(screen.getByText("ELEVATED")).toBeInTheDocument();
  });
});
