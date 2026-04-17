import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { StalenessChip } from "../src/primitives/StalenessChip";

describe("StalenessChip", () => {
  it("renders fresh state with no age label", () => {
    render(<StalenessChip state="fresh" ageDays={30} />);
    expect(screen.getByText(/fresh/i)).toBeInTheDocument();
  });

  it("renders yellow state with age in months", () => {
    render(<StalenessChip state="yellow" ageDays={200} />);
    const text = screen.getByText(/~7 months/i);
    expect(text).toBeInTheDocument();
  });

  it("renders red state with age in years for old data", () => {
    render(<StalenessChip state="red" ageDays={400} />);
    expect(screen.getByText(/~1 years?/i)).toBeInTheDocument();
  });

  it("renders missing state with em dash", () => {
    render(<StalenessChip state="missing" ageDays={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});
