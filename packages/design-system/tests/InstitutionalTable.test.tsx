import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { InstitutionalTable } from "../src/primitives/InstitutionalTable";

describe("InstitutionalTable", () => {
  it("renders column headers", () => {
    render(
      <InstitutionalTable
        columns={[
          { key: "agency", header: "Agency" },
          { key: "rating", header: "Rating" },
        ]}
        rows={[]}
      />,
    );
    expect(screen.getByText("Agency")).toBeInTheDocument();
    expect(screen.getByText("Rating")).toBeInTheDocument();
  });

  it("renders cells via render function", () => {
    render(
      <InstitutionalTable
        columns={[
          { key: "a", header: "A", render: (r: { a: string }) => r.a.toUpperCase() },
        ]}
        rows={[{ a: "hello" }, { a: "world" }]}
      />,
    );
    expect(screen.getByText("HELLO")).toBeInTheDocument();
    expect(screen.getByText("WORLD")).toBeInTheDocument();
  });

  it("shows empty state when rows are empty and emptyLabel provided", () => {
    render(
      <InstitutionalTable
        columns={[{ key: "a", header: "A" }]}
        rows={[]}
        emptyLabel="No data"
      />,
    );
    expect(screen.getByText("No data")).toBeInTheDocument();
  });
});
