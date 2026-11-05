import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { routerMock } from "@/test/setup";
import { json, mockFetch, renderWithIntl } from "@/test/utils";
import { LoginForm, RegisterForm } from "./auth-forms";

beforeEach(() => vi.clearAllMocks());

describe("LoginForm", () => {
  it("logs in and goes to the dashboard", async () => {
    const calls = mockFetch({ "POST /api/v1/auth/login": { id: "u" } });
    renderWithIntl(<LoginForm />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Email"), "a@example.com");
    await user.type(screen.getByLabelText("Password"), "secret-password");
    await user.click(screen.getByRole("button", { name: "Log in" }));
    await waitFor(() => expect(routerMock.push).toHaveBeenCalledWith("/dashboard"));
    expect(JSON.parse(calls[0].init.body as string)).toEqual({ email: "a@example.com", password: "secret-password" });
  });

  it("shows the server error", async () => {
    mockFetch({
      "POST /api/v1/auth/login": () => json({ error: { code: "unauthorized", message: "Invalid email or password" } }, 401),
    });
    renderWithIntl(<LoginForm />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Email"), "a@example.com");
    await user.type(screen.getByLabelText("Password"), "x");
    await user.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByText("Invalid email or password")).toBeInTheDocument();
  });
});

describe("RegisterForm", () => {
  it("registers a broker with an agency", async () => {
    const calls = mockFetch({ "POST /api/v1/auth/register": { id: "u" } });
    renderWithIntl(<RegisterForm locale="ar" />, "ar");
    const user = userEvent.setup();
    await user.click(screen.getByLabelText("وسيط عقاري"));
    await user.type(screen.getByLabelText("الاسم الكامل"), "Rami Broker");
    await user.type(screen.getByLabelText("البريد الإلكتروني"), "r@example.com");
    await user.type(screen.getByLabelText("رقم الهاتف"), "70123456");
    await user.type(screen.getByLabelText("اسم الوكالة (اختياري)"), "Cedar");
    await user.type(screen.getByLabelText("كلمة المرور"), "long-password-1");
    await user.click(screen.getByRole("button", { name: "إنشاء الحساب" }));
    await waitFor(() => expect(routerMock.push).toHaveBeenCalledWith("/dashboard"));
    expect(JSON.parse(calls[0].init.body as string)).toMatchObject({
      role: "broker", organization_name: "Cedar", phone: "70123456", locale: "ar",
    });
  });

  it("sends seekers to the listings page and omits agency", async () => {
    const calls = mockFetch({ "POST /api/v1/auth/register": { id: "u" } });
    renderWithIntl(<RegisterForm locale="en" />);
    const user = userEvent.setup();
    await user.click(screen.getByLabelText("Looking for a home"));
    expect(screen.queryByLabelText("Agency name (optional)")).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("Full name"), "Sara");
    await user.type(screen.getByLabelText("Email"), "s@example.com");
    await user.type(screen.getByLabelText("Password"), "long-password-1");
    await user.click(screen.getByRole("button", { name: "Create account" }));
    await waitFor(() => expect(routerMock.push).toHaveBeenCalledWith("/listings"));
    expect(JSON.parse(calls[0].init.body as string)).toMatchObject({ role: "seeker", organization_name: null, phone: null });
  });

  it("shows a network error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    renderWithIntl(<RegisterForm locale="en" />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Full name"), "Sara");
    await user.type(screen.getByLabelText("Email"), "s@example.com");
    await user.type(screen.getByLabelText("Password"), "long-password-1");
    await user.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("Network error. Check your connection.")).toBeInTheDocument();
  });
});
