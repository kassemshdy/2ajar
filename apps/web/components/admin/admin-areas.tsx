"use client";

import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import type { AreaProfile, AreaProfileInput, Location } from "@2ajar/contracts";
import { api, ApiError } from "@/lib/api-client";
import { formatDate } from "@/lib/format";
import { Button } from "../ui/button";
import { Alert, Badge, Card } from "../ui/card";
import { Field, Input, Select, Textarea } from "../ui/input";

const GARBAGE = ["daily", "several_weekly", "weekly", "irregular"];
const FLOOD = ["low", "medium", "high"];

const num = (v: FormDataEntryValue | null) => (v === null || v === "" ? null : Number(v));
const str = (v: FormDataEntryValue | null) => (v === null || String(v).trim() === "" ? null : String(v).trim());

/**
 * Staff editor for neighbourhood facts (safety, thefts, noise, garbage, flooding). A profile on a district or
 * governorate applies to every area below it that has no profile of its own.
 */
export function AdminAreas() {
  const t = useTranslations("adminAreas");
  const ta = useTranslations("area");
  const tErr = useTranslations("errors");
  const locale = useLocale();
  const [locations, setLocations] = useState<Location[]>([]);
  const [profiles, setProfiles] = useState<AreaProfile[]>([]);
  const [selected, setSelected] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [locs, areas] = await Promise.all([api<Location[]>("/locations"), api<AreaProfile[]>("/admin/areas")]);
      setLocations(locs);
      setProfiles(areas);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : tErr("generic"));
    }
  }, [tErr]);

  useEffect(() => {
    load();
  }, [load]);

  const name = (l: Pick<Location, "name_en" | "name_ar">) => (locale === "ar" ? l.name_ar : l.name_en);
  const location = locations.find((l) => l.id === selected);
  const current = location ? profiles.find((p) => p.location_slug === location.slug) : undefined;

  async function save(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!location) return;
    const fd = new FormData(e.currentTarget);
    const body: AreaProfileInput = {
      safety_score: num(fd.get("safety_score")),
      quiet_score: num(fd.get("quiet_score")),
      theft_reports_12m: num(fd.get("theft_reports_12m")),
      garbage_collection: str(fd.get("garbage_collection")) as AreaProfileInput["garbage_collection"],
      flood_risk: str(fd.get("flood_risk")) as AreaProfileInput["flood_risk"],
      noise_notes_en: str(fd.get("noise_notes_en")),
      noise_notes_ar: str(fd.get("noise_notes_ar")),
      summary_en: str(fd.get("summary_en")),
      summary_ar: str(fd.get("summary_ar")),
      source_note: str(fd.get("source_note")),
    };
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await api<AreaProfile>(`/admin/areas/${location.id}`, { method: "PUT", json: body });
      setNotice(t("saved"));
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : tErr("generic"));
    } finally {
      setBusy(false);
    }
  }

  const scoreSelect = (id: string, value: number | null | undefined) => (
    <Select id={id} name={id} defaultValue={value ?? ""}>
      <option value="">—</option>
      {[1, 2, 3, 4, 5].map((n) => (
        <option key={n} value={n}>
          {n}
        </option>
      ))}
    </Select>
  );

  return (
    <div className="flex flex-col gap-4" data-testid="admin-areas">
      <p className="text-sm text-muted-foreground">{t("intro")}</p>
      {error ? <Alert tone="error">{error}</Alert> : null}
      {notice ? <Alert tone="success">{notice}</Alert> : null}

      <Card className="p-4">
        <Field label={t("location")} htmlFor="area-location">
          <Select id="area-location" value={selected} onChange={(e) => setSelected(e.target.value)}>
            <option value="">—</option>
            {locations.map((l) => {
              const has = profiles.some((p) => p.location_slug === l.slug);
              return (
                <option key={l.id} value={l.id}>
                  {"  ".repeat(l.path.split("/").length - 1) + name(l) + (has ? " ✓" : "")}
                </option>
              );
            })}
          </Select>
        </Field>
      </Card>

      {location ? (
        <form onSubmit={save} key={`${location.id}-${current?.updated_at ?? "new"}`} data-testid="area-form">
          <Card className="grid gap-4 p-4 sm:grid-cols-2">
            <div className="flex flex-wrap items-center gap-2 sm:col-span-2">
              <h2 className="font-semibold">{name(location)}</h2>
              {current?.is_demo ? <Badge tone="demo">{ta("demo")}</Badge> : null}
              {current ? (
                <span className="text-xs text-muted-foreground">
                  {ta("curated", { date: formatDate(current.updated_at, locale) })}
                </span>
              ) : null}
            </div>
            <Field label={`${ta("safety")} (1–5)`} htmlFor="safety_score">
              {scoreSelect("safety_score", current?.safety_score)}
            </Field>
            <Field label={`${ta("quiet")} (1–5)`} htmlFor="quiet_score">
              {scoreSelect("quiet_score", current?.quiet_score)}
            </Field>
            <Field label={t("thefts")} htmlFor="theft_reports_12m">
              <Input
                id="theft_reports_12m"
                name="theft_reports_12m"
                type="number"
                min={0}
                defaultValue={current?.theft_reports_12m ?? undefined}
              />
            </Field>
            <Field label={ta("garbage")} htmlFor="garbage_collection">
              <Select id="garbage_collection" name="garbage_collection" defaultValue={current?.garbage_collection ?? ""}>
                <option value="">—</option>
                {GARBAGE.map((v) => (
                  <option key={v} value={v}>
                    {ta(`garbageKind.${v}`)}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={ta("flood")} htmlFor="flood_risk">
              <Select id="flood_risk" name="flood_risk" defaultValue={current?.flood_risk ?? ""}>
                <option value="">—</option>
                {FLOOD.map((v) => (
                  <option key={v} value={v}>
                    {ta(`floodKind.${v}`)}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("source")} htmlFor="source_note" hint={t("sourceHint")}>
              <Input id="source_note" name="source_note" maxLength={300} defaultValue={current?.source_note ?? ""} />
            </Field>
            <Field label={`${ta("noise")} (EN)`} htmlFor="noise_notes_en">
              <Input id="noise_notes_en" name="noise_notes_en" dir="ltr" maxLength={300} defaultValue={current?.noise_notes_en ?? ""} />
            </Field>
            <Field label={`${ta("noise")} (AR)`} htmlFor="noise_notes_ar">
              <Input id="noise_notes_ar" name="noise_notes_ar" dir="rtl" maxLength={300} defaultValue={current?.noise_notes_ar ?? ""} />
            </Field>
            <Field label={t("summaryEn")} htmlFor="summary_en">
              <Textarea id="summary_en" name="summary_en" dir="ltr" maxLength={2000} defaultValue={current?.summary_en ?? ""} />
            </Field>
            <Field label={t("summaryAr")} htmlFor="summary_ar">
              <Textarea id="summary_ar" name="summary_ar" dir="rtl" maxLength={2000} defaultValue={current?.summary_ar ?? ""} />
            </Field>
            <Button type="submit" disabled={busy} className="sm:col-span-2" data-testid="save-area">
              {t("save")}
            </Button>
          </Card>
        </form>
      ) : null}
    </div>
  );
}
