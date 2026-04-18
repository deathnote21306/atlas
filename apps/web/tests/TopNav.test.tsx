import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

describe("Sidebar", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ email: "a@b.test", role: "Analyst" }), { status: 200 })),
    );
  });

  it("renders Atlas brand and navigation sections", async () => {
    render(wrap(<Sidebar />));
    expect(screen.getByText(/atlas/i)).toBeInTheDocument();
    expect(screen.getByText(/intelligence/i)).toBeInTheDocument();
    expect(screen.getByText(/operations/i)).toBeInTheDocument();
  });

  it("renders nav links for Dashboard, Countries, Scenarios, and News", async () => {
    render(wrap(<Sidebar />));
    expect(await screen.findByRole("link", { name: /dashboard/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /country intelligence/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /scenario engine/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /news & events/i })).toBeInTheDocument();
  });

  it("shows disabled items with Soon badges", async () => {
    render(wrap(<Sidebar />));
    const badges = screen.getAllByText(/soon/i);
    expect(badges.length).toBe(3);
  });

  it("shows the signed-in email and Logout button when authed", async () => {
    render(wrap(<Sidebar />));
    expect(await screen.findByText(/a@b\.test/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /logout/i })).toBeInTheDocument();
  });

  it("calls logout when the button is clicked", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ email: "a@b.test", role: "Analyst" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    render(wrap(<Sidebar />));
    const btn = await screen.findByRole("button", { name: /logout/i });
    await userEvent.click(btn);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/logout",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
