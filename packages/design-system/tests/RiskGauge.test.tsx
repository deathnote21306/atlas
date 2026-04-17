import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { RiskGauge } from "../src/primitives/RiskGauge";

describe("RiskGauge", () => {
  it("renders label and numeric score", () => {
    render(<RiskGauge label="Debt Burden" score={7} rationale="public debt 85%" />);
    expect(screen.getByText("Debt Burden")).toBeInTheDocument();
    expect(screen.getByText("7/10")).toBeInTheDocument();
  });

  it("shows rationale", () => {
    render(<RiskGauge label="FX Stability" score={3} rationale="30d move -4%" />);
    expect(screen.getByText(/30d move -4%/)).toBeInTheDocument();
  });

  it("applies danger styling for high scores", () => {
    const { container } = render(<RiskGauge label="X" score={9} rationale="r" />);
    expect(container.innerHTML).toMatch(/bg-danger/);
  });

  it("applies positive styling for low scores", () => {
    const { container } = render(<RiskGauge label="X" score={1} rationale="r" />);
    expect(container.innerHTML).toMatch(/bg-positive/);
  });

  it("marks estimates with a visible flag", () => {
    render(<RiskGauge label="X" score={5} rationale="no data" isEstimate />);
    expect(screen.getByText(/estimate/i)).toBeInTheDocument();
  });
});
