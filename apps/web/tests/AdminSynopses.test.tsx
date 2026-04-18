import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "../src/auth/AuthContext";
import AdminSynopses from "../src/routes/AdminSynopses";
import { toast } from "../src/components/Toast";

vi.mock("../src/components/Toast", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const SYNOPSES = [
  {
    id: "s1",
    iso3: "GHA",
    text: "Ghana synopsis text here",
    generated_at: "2026-04-17T10:00:00Z",
    approval_state: "pending",
  },
];

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <AuthProvider>{ui}</AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function stubFetch({
  synopses = SYNOPSES,
  approveStatus = 200,
}: { synopses?: typeof SYNOPSES; approveStatus?: number } = {}) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (url === "/api/me") {
        return Promise.resolve(
          new Response(JSON.stringify({ email: "a@b.test", role: "Admin" }), { status: 200 }),
        );
      }
      if (typeof url === "string" && url.includes("/approve") && init?.method === "POST") {
        if (approveStatus !== 200) {
          return Promise.resolve(
            new Response(JSON.stringify({ detail: "Server error" }), { status: approveStatus }),
          );
        }
        return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
      }
      // Default: list synopses
      return Promise.resolve(
        new Response(JSON.stringify(synopses), { status: 200 }),
      );
    }),
  );
}

describe("AdminSynopses", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    // Re-mock toast after restoreAllMocks
    (toast.success as ReturnType<typeof vi.fn>) = vi.fn();
    (toast.error as ReturnType<typeof vi.fn>) = vi.fn();
  });

  it("shows error toast on failed approve mutation", async () => {
    stubFetch({ approveStatus: 500 });
    render(wrap(<AdminSynopses />));

    const approveBtn = await screen.findByRole("button", { name: /approve/i });
    await userEvent.click(approveBtn);

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Server error");
    });
  });

  it("shows success toast on successful approve", async () => {
    stubFetch({ approveStatus: 200 });
    render(wrap(<AdminSynopses />));

    const approveBtn = await screen.findByRole("button", { name: /approve/i });
    await userEvent.click(approveBtn);

    await waitFor(() => {
      expect(toast.success).toHaveBeenCalledWith("Synopsis approved");
    });
  });
});
