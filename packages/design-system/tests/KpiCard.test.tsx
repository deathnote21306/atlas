// packages/design-system/tests/KpiCard.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { KpiCard } from "../src/primitives/KpiCard";

describe("KpiCard", () => {
  it("renders label and value", () => {
    render(<KpiCard label="Debt / GDP" value="62.4%" />);
    expect(screen.getByText("Debt / GDP")).toBeInTheDocument();
    expect(screen.getByText("62.4%")).toBeInTheDocument();
  });

  it("renders hint when provided", () => {
    render(<KpiCard label="FX" value="15.2" hint="USD/NGN" />);
    expect(screen.getByText("USD/NGN")).toBeInTheDocument();
  });
});
