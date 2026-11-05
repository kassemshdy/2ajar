"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import type { User } from "@2ajar/contracts";
import { Link, useRouter } from "@/i18n/navigation";
import { api, ApiError } from "@/lib/api-client";
import { Button } from "./ui/button";
import { Alert, Card } from "./ui/card";
import { Field, Input } from "./ui/input";

function useSubmit() {
  const tErr = useTranslations("errors");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof ApiError && e.status ? e.message : tErr("network"));
    } finally {
      setBusy(false);
    }
  }
  return { error, busy, run };
}

export function LoginForm() {
  const t = useTranslations("auth");
  const router = useRouter();
  const { error, busy, run } = useSubmit();

  return (
    <Card className="mx-auto w-full max-w-md p-6">
      <h1 className="mb-4 text-2xl font-bold">{t("loginTitle")}</h1>
      <form
        className="flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          const fd = new FormData(e.currentTarget);
          run(async () => {
            await api<User>("/auth/login", { json: { email: fd.get("email"), password: fd.get("password") } });
            router.push("/dashboard");
            router.refresh();
          });
        }}
      >
        <Field label={t("email")} htmlFor="email">
          <Input id="email" name="email" type="email" required dir="ltr" autoComplete="email" />
        </Field>
        <Field label={t("password")} htmlFor="password">
          <Input id="password" name="password" type="password" required autoComplete="current-password" />
        </Field>
        {error ? <Alert tone="error">{error}</Alert> : null}
        <Button type="submit" disabled={busy}>
          {t("submitLogin")}
        </Button>
        <p className="text-center text-sm text-muted-foreground">
          {t("noAccount")}{" "}
          <Link href="/register" className="font-medium text-primary">
            {t("registerTitle")}
          </Link>
        </p>
      </form>
    </Card>
  );
}

export function RegisterForm({ locale }: { locale: string }) {
  const t = useTranslations("auth");
  const router = useRouter();
  const { error, busy, run } = useSubmit();
  const [role, setRole] = useState<"seeker" | "owner" | "broker">("owner");

  return (
    <Card className="mx-auto w-full max-w-md p-6">
      <h1 className="mb-4 text-2xl font-bold">{t("registerTitle")}</h1>
      <form
        className="flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          const fd = new FormData(e.currentTarget);
          run(async () => {
            await api<User>("/auth/register", {
              json: {
                email: fd.get("email"),
                password: fd.get("password"),
                full_name: fd.get("full_name"),
                phone: fd.get("phone") || null,
                role,
                organization_name: role === "broker" ? fd.get("organization_name") || null : null,
                locale,
              },
            });
            router.push(role === "seeker" ? "/listings" : "/dashboard");
            router.refresh();
          });
        }}
      >
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 text-sm font-medium">{t("role")}</legend>
          {(["seeker", "owner", "broker"] as const).map((r) => (
            <label
              key={r}
              className="flex cursor-pointer items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm has-[:checked]:border-primary has-[:checked]:bg-primary/5"
            >
              <input type="radio" name="role" value={r} checked={role === r} onChange={() => setRole(r)} />
              {t(`role_${r}`)}
            </label>
          ))}
        </fieldset>
        <Field label={t("fullName")} htmlFor="full_name">
          <Input id="full_name" name="full_name" required minLength={2} autoComplete="name" />
        </Field>
        <Field label={t("email")} htmlFor="email">
          <Input id="email" name="email" type="email" required dir="ltr" autoComplete="email" />
        </Field>
        <Field label={t("phone")} htmlFor="phone">
          <Input id="phone" name="phone" type="tel" dir="ltr" autoComplete="tel" placeholder="+961 …" />
        </Field>
        {role === "broker" ? (
          <Field label={t("organization")} htmlFor="organization_name">
            <Input id="organization_name" name="organization_name" minLength={2} />
          </Field>
        ) : null}
        <Field label={t("password")} htmlFor="password" hint={t("passwordHint")}>
          <Input id="password" name="password" type="password" required minLength={10} autoComplete="new-password" />
        </Field>
        {error ? <Alert tone="error">{error}</Alert> : null}
        <Button type="submit" disabled={busy}>
          {t("submitRegister")}
        </Button>
        <p className="text-center text-sm text-muted-foreground">
          {t("haveAccount")}{" "}
          <Link href="/login" className="font-medium text-primary">
            {t("loginTitle")}
          </Link>
        </p>
      </form>
    </Card>
  );
}
