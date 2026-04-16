import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import Login from "../src/routes/Login";
import { AuthProvider } from "../src/auth/AuthContext";

function wrap(ui: React.ReactNode) {
  return <MemoryRouter><AuthProvider>{ui}</AuthProvider></MemoryRouter>;
}

describe("Login", () => {
  it("shows invalid-credentials error on 401", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response("{}", { status: 401 }))  // /api/me initial
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "invalid credentials" }), { status: 401 })); // login
    vi.stubGlobal("fetch", fetchMock);

    render(wrap(<Login />));
    await userEvent.type(screen.getByLabelText(/email/i), "a@b.test");
    await userEvent.type(screen.getByLabelText(/password/i), "wrong");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/invalid credentials/i);
  });
});
