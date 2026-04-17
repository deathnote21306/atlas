import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import TopNav from "../src/components/TopNav";
import { AuthProvider } from "../src/auth/AuthContext";

function wrap(ui: React.ReactNode) {
  return (
    <MemoryRouter>
      <AuthProvider>{ui}</AuthProvider>
    </MemoryRouter>
  );
}

describe("TopNav", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ email: "a@b.test", role: "Analyst" }), { status: 200 })),
    );
  });

  it("renders Atlas logo + Home and Countries links", async () => {
    render(wrap(<TopNav />));
    expect(screen.getByText(/atlas/i)).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /home/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /countries/i })).toBeInTheDocument();
  });

  it("shows the signed-in email and Logout button when authed", async () => {
    render(wrap(<TopNav />));
    expect(await screen.findByText(/a@b\.test/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /logout/i })).toBeInTheDocument();
  });

  it("calls logout when the button is clicked", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ email: "a@b.test", role: "Analyst" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    render(wrap(<TopNav />));
    const btn = await screen.findByRole("button", { name: /logout/i });
    await userEvent.click(btn);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/logout",
      expect.objectContaining({ method: "POST" }),
    );
  });
});
