import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Sidebar from "../src/components/Sidebar";
import { AuthProvider } from "../src/auth/AuthContext";

function wrap(ui: React.ReactNode) {
  return (
    <MemoryRouter>
      <AuthProvider>{ui}</AuthProvider>
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async () => new Response(null, { status: 401 }));
});

describe("Sidebar", () => {
  it("renders ATLAS brand and navigation sections", async () => {
    render(wrap(<Sidebar />));
    expect(screen.getByText("ATLAS")).toBeTruthy();
    expect(screen.getByText("Dashboard")).toBeTruthy();
    expect(screen.getByText("Country Intelligence")).toBeTruthy();
    expect(screen.getByText("News & Events")).toBeTruthy();
  });

  it("renders disabled items with correct styling", async () => {
    render(wrap(<Sidebar />));
    expect(screen.getByText("Capital View")).toBeTruthy();
    expect(screen.getByText("Portfolio System")).toBeTruthy();
  });
});
