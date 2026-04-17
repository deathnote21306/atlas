import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { RatingBadge } from "../src/primitives/RatingBadge";

describe("RatingBadge", () => {
  it("renders agency and rating", () => {
    render(<RatingBadge agency="S&P" rating="B+" />);
    expect(screen.getByText("S&P")).toBeInTheDocument();
    expect(screen.getByText("B+")).toBeInTheDocument();
  });

  it("renders outlook when provided", () => {
    render(<RatingBadge agency="Moodys" rating="Ba2" outlook="positive" />);
    expect(screen.getByText(/positive/i)).toBeInTheDocument();
  });

  it("applies distressed styling for SD/D/RD/C ratings", () => {
    const { container } = render(<RatingBadge agency="S&P" rating="SD" />);
    const el = container.firstChild as HTMLElement;
    expect(el.className).toMatch(/bg-danger/);
  });
});
