import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { seekerUser, staffUser } from "@/test/support-fixtures";
import { json, mockFetch, renderWithIntl } from "@/test/utils";
import { ApiTokens, mcpConfig } from "./api-tokens";

describe("ApiTokens", () => {
  it("creates a token, shows it once with MCP config, copies and revokes", async () => {
    const calls = mockFetch({
      "GET /api/v1/me/api-tokens": [
        { id: "k1", name: "Old", prefix: "2ajar_abcdef", created_at: "2026-11-01T00:00:00Z", expires_at: null,
          last_used_at: "2026-11-02T00:00:00Z", revoked_at: null },
      ],
      "GET /api/v1/me": staffUser,
      "POST /api/v1/me/api-tokens": () =>
        json({ id: "k2", name: "Claude", prefix: "2ajar_secret", created_at: "2026-11-03T00:00:00Z",
               expires_at: null, last_used_at: null, revoked_at: null, token: "2ajar_secretvalue" }, 201),
      "DELETE /api/v1/me/api-tokens/k1": 204,
    });
    renderWithIntl(<ApiTokens />);
    expect(await screen.findByText(/Last used/)).toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(screen.getByTestId("token-create"));
    expect(await screen.findByTestId("token-value")).toHaveTextContent("2ajar_secretvalue");
    expect(screen.getByText(/"Authorization": "Bearer 2ajar_secretvalue"/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Copy" }));
    expect(await navigator.clipboard.readText()).toBe("2ajar_secretvalue"); // userEvent provides the clipboard
    expect(screen.getByRole("button", { name: "Copied" })).toBeInTheDocument();
    expect(JSON.parse(calls.find((c) => c.method === "POST")!.init.body as string)).toEqual({
      name: "Claude",
      expires_in_days: 90,
    });
    const revokeButtons = screen.getAllByRole("button", { name: "Revoke" });
    await user.click(revokeButtons[revokeButtons.length - 1]);
    expect(await screen.findByText("Revoked")).toBeInTheDocument();
    expect(screen.getByText("Never used")).toBeInTheDocument();
  });

  it("shows errors and denies accounts without mcp.access", async () => {
    mockFetch({
      "GET /api/v1/me/api-tokens": [],
      "GET /api/v1/me": staffUser,
      "POST /api/v1/me/api-tokens": () => json({ error: { code: "forbidden", message: "At most 10 active tokens" } }, 403),
    });
    renderWithIntl(<ApiTokens />);
    expect(await screen.findByText("No tokens yet.")).toBeInTheDocument();
    await userEvent.setup().click(screen.getByTestId("token-create"));
    expect(await screen.findByText("At most 10 active tokens")).toBeInTheDocument();

    mockFetch({ "GET /api/v1/me": seekerUser });
    renderWithIntl(<ApiTokens />);
    expect(await screen.findByText("Your account cannot create API tokens.")).toBeInTheDocument();
  });

  it("builds an MCP client config", () => {
    expect(JSON.parse(mcpConfig("https://x.test", "t"))).toEqual({
      mcpServers: { "2ajar": { type: "http", url: "https://x.test/api/v1/mcp", headers: { Authorization: "Bearer t" } } },
    });
  });
});
