"use client";

import { ImagePlus, Trash2 } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import type { ListingPrivate, Location } from "@2ajar/contracts";
import { Link, useRouter } from "@/i18n/navigation";
import { api, ApiError } from "@/lib/api-client";
import { Button, buttonVariants } from "./ui/button";
import { Alert, Card } from "./ui/card";
import { Field, Input, Select, Textarea } from "./ui/input";

const PROPERTY_TYPES = ["apartment", "studio", "duplex", "house", "villa", "chalet", "office", "shop", "land"];
const AMENITIES = [
  "generator_24_7", "solar_power", "elevator", "parking", "balcony", "terrace", "sea_view", "mountain_view",
  "air_conditioning", "central_heating", "water_tank", "security", "concierge", "gym", "pool", "garden",
  "storage", "pets_allowed",
];

function errorText(e: unknown, fallback: string) {
  if (e instanceof ApiError && e.status) {
    if (Array.isArray(e.details) && e.details.every((d) => typeof d === "string")) return e.details.join(" · ");
    return e.message;
  }
  return fallback;
}

const num = (v: FormDataEntryValue | null) => (v === null || v === "" ? null : Number(v));
const str = (v: FormDataEntryValue | null) => (v === null || v === "" ? null : String(v));
const bool = (v: FormDataEntryValue | null) => (v === "yes" ? true : v === "no" ? false : null);
const triState = (v: boolean | null | undefined) => (v === true ? "yes" : v === false ? "no" : "");
/** One bullet per line; blank lines dropped (the API trims and caps the list). */
const lines = (v: FormDataEntryValue | null) =>
  String(v ?? "")
    .split("\n")
    .map((x) => x.trim())
    .filter(Boolean);

const PERIODS = ["hourly", "daily", "nightly", "weekly", "monthly", "yearly"];
const ELECTRICITY = ["edl_only", "edl_plus_generator", "generator_24_7", "solar", "solar_battery"];
const WATER = ["municipal", "well", "tanker", "mixed"];
const SEWAGE = ["public_network", "septic_tank"];
const WINTER = ["warm", "moderate", "cold"];
const SUMMER = ["cool", "moderate", "hot"];

export function ListingForm({ locations, listingId }: { locations: Location[]; listingId?: string }) {
  const t = useTranslations("form");
  const te = useTranslations("enums");
  const tErr = useTranslations("errors");
  const tl = useTranslations("living");
  const locale = useLocale();
  const router = useRouter();
  const [listing, setListing] = useState<ListingPrivate | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    if (!listingId) return;
    try {
      const l = await api<ListingPrivate>(`/listings/${listingId}`);
      setListing(l);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.replace("/login");
      else setError(errorText(e, tErr("generic")));
    }
  }, [listingId, router, tErr]);

  useEffect(() => {
    reload();
  }, [reload]);

  if (listingId && !listing) return error ? <Alert tone="error">{error}</Alert> : null;

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const payload = {
      transaction_type: "rent", // 2ajar is rentals only, from an hour to years
      property_type: fd.get("property_type"),
      location_id: fd.get("location_id"),
      price_usd: num(fd.get("price_usd")),
      price_period: fd.get("price_period"),
      bedrooms: num(fd.get("bedrooms")),
      bathrooms: num(fd.get("bathrooms")),
      area_sqm: num(fd.get("area_sqm")),
      floor: num(fd.get("floor")),
      max_guests: num(fd.get("max_guests")),
      furnished: str(fd.get("furnished")),
      amenities: fd.getAll("amenities"),
      title_en: str(fd.get("title_en")),
      title_ar: str(fd.get("title_ar")),
      description_en: str(fd.get("description_en")),
      description_ar: str(fd.get("description_ar")),
      contact_whatsapp: str(fd.get("contact_whatsapp")),
      electricity_supply: str(fd.get("electricity_supply")),
      generator_amps: num(fd.get("generator_amps")),
      electricity_usd_month: num(fd.get("electricity_usd_month")),
      water_source: str(fd.get("water_source")),
      water_usd_month: num(fd.get("water_usd_month")),
      sewage: str(fd.get("sewage")),
      parking_spots: num(fd.get("parking_spots")),
      solar_ready: bool(fd.get("solar_ready")),
      elevator_backup: bool(fd.get("elevator_backup")),
      winter_comfort: str(fd.get("winter_comfort")),
      summer_comfort: str(fd.get("summer_comfort")),
      highlights: lines(fd.get("highlights")),
      things_to_know: lines(fd.get("things_to_know")),
    };
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      if (listingId) {
        setListing(await api<ListingPrivate>(`/listings/${listingId}`, { method: "PATCH", json: payload }));
        setNotice(t("saved"));
      } else {
        const created = await api<ListingPrivate>("/listings", { json: payload });
        router.push(`/dashboard/listings/${created.id}/edit`);
      }
    } catch (err) {
      setError(errorText(err, tErr("generic")));
    } finally {
      setBusy(false);
    }
  }

  async function upload(files: FileList | null) {
    if (!files || !listingId) return;
    setBusy(true);
    setError(null);
    try {
      for (const file of Array.from(files)) {
        const form = new FormData();
        form.append("file", file);
        await api(`/listings/${listingId}/media`, { form });
      }
      await reload();
    } catch (err) {
      setError(errorText(err, tErr("generic")));
    } finally {
      setBusy(false);
    }
  }

  async function removeMedia(mediaId: string) {
    await api(`/listings/${listingId}/media/${mediaId}`, { method: "DELETE" }).catch((err) =>
      setError(errorText(err, tErr("generic"))),
    );
    await reload();
  }

  async function publish() {
    setError(null);
    try {
      setListing(await api<ListingPrivate>(`/listings/${listingId}/publish`, { method: "POST" }));
      setNotice(t("published"));
    } catch (err) {
      setError(errorText(err, tErr("generic")));
    }
  }

  const l = listing;
  const lv = l?.property.living;
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <h1 className="text-2xl font-bold">{listingId ? t("editTitle") : t("createTitle")}</h1>
      {error ? <Alert tone="error" data-testid="form-error">{error}</Alert> : null}
      {notice ? <Alert tone="success" data-testid="form-notice">{notice}</Alert> : null}

      {listingId && l ? (
        <Card className="flex flex-col gap-3 p-4">
          <h2 className="font-semibold">{t("photos")}</h2>
          <ul className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {l.media.map((m) => (
              <li key={m.id} className="group relative aspect-[4/3] overflow-hidden rounded-lg bg-muted">
                <img src={m.url} alt="" className="size-full object-cover" />
                <button
                  type="button"
                  onClick={() => removeMedia(m.id)}
                  className="absolute end-1 top-1 rounded-md bg-background/90 p-1 text-destructive"
                  aria-label={t("remove")}
                >
                  <Trash2 className="size-4" />
                </button>
              </li>
            ))}
          </ul>
          <label className={buttonVariants({ variant: "outline" }) + " cursor-pointer self-start"}>
            <ImagePlus className="size-4" aria-hidden />
            {busy ? t("uploading") : t("addPhotos")}
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              multiple
              className="sr-only"
              data-testid="photo-input"
              onChange={(e) => upload(e.target.files)}
            />
          </label>
          <p className="text-xs text-muted-foreground">{t("photosHint")}</p>
          <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
            {l.status !== "published" ? (
              <Button type="button" onClick={publish} data-testid="publish-button">
                {t("publishNow")}
              </Button>
            ) : (
              <Link href={`/listings/${l.id}`} className={buttonVariants({ variant: "outline" })} data-testid="view-live">
                {locale === "ar" ? "عرض الإعلان" : "View listing"}
              </Link>
            )}
          </div>
        </Card>
      ) : null}

      <form onSubmit={submit} className="flex flex-col gap-6" key={l?.updated_at ?? "new"} data-testid="listing-form">
        <Card className="grid gap-4 p-4 sm:grid-cols-2">
          <Field label={t("propertyType")} htmlFor="property_type">
            <Select id="property_type" name="property_type" defaultValue={l?.property.property_type ?? "apartment"}>
              {PROPERTY_TYPES.map((v) => <option key={v} value={v}>{te(v)}</option>)}
            </Select>
          </Field>
          <Field label={t("location")} htmlFor="location_id">
            <Select id="location_id" name="location_id" required defaultValue={l?.location_id ?? ""}>
              <option value="" disabled>—</option>
              {locations.map((loc) => (
                <option key={loc.id} value={loc.id} disabled={loc.level !== "area"}>
                  {"  ".repeat(loc.path.split("/").length - 1) + (locale === "ar" ? loc.name_ar : loc.name_en)}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("price")} htmlFor="price_usd">
            <Input id="price_usd" name="price_usd" type="number" min={1} required inputMode="numeric" defaultValue={l?.price_usd} />
          </Field>
          <Field label={t("pricePeriod")} htmlFor="price_period" hint={t("pricePeriodHint")}>
            <Select
              id="price_period"
              name="price_period"
              defaultValue={l && l.price_period !== "total" ? l.price_period : "monthly"}
            >
              {PERIODS.map((v) => <option key={v} value={v}>{te(v)}</option>)}
            </Select>
          </Field>
          <Field label={t("bedrooms")} htmlFor="bedrooms">
            <Input id="bedrooms" name="bedrooms" type="number" min={0} max={20} defaultValue={l?.property.bedrooms ?? undefined} />
          </Field>
          <Field label={t("maxGuests")} htmlFor="max_guests">
            <Input id="max_guests" name="max_guests" type="number" min={1} max={200} defaultValue={l?.property.max_guests ?? undefined} />
          </Field>
          <Field label={t("bathrooms")} htmlFor="bathrooms">
            <Input id="bathrooms" name="bathrooms" type="number" min={0} max={20} defaultValue={l?.property.bathrooms ?? undefined} />
          </Field>
          <Field label={t("area")} htmlFor="area_sqm">
            <Input id="area_sqm" name="area_sqm" type="number" min={1} defaultValue={l?.property.area_sqm ?? undefined} />
          </Field>
          <Field label={t("floor")} htmlFor="floor">
            <Input id="floor" name="floor" type="number" min={-5} max={100} defaultValue={l?.property.floor ?? undefined} />
          </Field>
          <Field label={t("furnished")} htmlFor="furnished">
            <Select id="furnished" name="furnished" defaultValue={l?.property.furnished ?? ""}>
              <option value="">—</option>
              {["furnished", "semi", "unfurnished"].map((v) => <option key={v} value={v}>{te(v)}</option>)}
            </Select>
          </Field>
        </Card>

        <Card className="flex flex-col gap-3 p-4">
          <h2 className="font-semibold">{t("amenities")}</h2>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {AMENITIES.map((a) => (
              <label key={a} className="flex items-center gap-2 text-sm">
                <input type="checkbox" name="amenities" value={a} defaultChecked={l?.property.amenities.includes(a)} className="size-4" />
                {te(a)}
              </label>
            ))}
          </div>
        </Card>

        <Card className="grid gap-4 p-4 sm:grid-cols-2" data-testid="living-fields">
          <div className="sm:col-span-2">
            <h2 className="font-semibold">{tl("title")}</h2>
            <p className="text-xs text-muted-foreground">{t("livingHint")}</p>
          </div>
          <Field label={tl("electricity")} htmlFor="electricity_supply">
            <Select id="electricity_supply" name="electricity_supply" defaultValue={lv?.electricity_supply ?? ""}>
              <option value="">—</option>
              {ELECTRICITY.map((v) => <option key={v} value={v}>{tl(`electricitySupply.${v}`)}</option>)}
            </Select>
          </Field>
          <Field label={t("generatorAmps")} htmlFor="generator_amps">
            <Input id="generator_amps" name="generator_amps" type="number" min={1} max={100} defaultValue={lv?.generator_amps ?? undefined} />
          </Field>
          <Field label={t("electricityBill")} htmlFor="electricity_usd_month">
            <Input id="electricity_usd_month" name="electricity_usd_month" type="number" min={0} max={5000} defaultValue={lv?.electricity_usd_month ?? undefined} />
          </Field>
          <Field label={tl("water")} htmlFor="water_source">
            <Select id="water_source" name="water_source" defaultValue={lv?.water_source ?? ""}>
              <option value="">—</option>
              {WATER.map((v) => <option key={v} value={v}>{tl(`waterSource.${v}`)}</option>)}
            </Select>
          </Field>
          <Field label={t("waterBill")} htmlFor="water_usd_month">
            <Input id="water_usd_month" name="water_usd_month" type="number" min={0} max={2000} defaultValue={lv?.water_usd_month ?? undefined} />
          </Field>
          <Field label={tl("sewage")} htmlFor="sewage">
            <Select id="sewage" name="sewage" defaultValue={lv?.sewage ?? ""}>
              <option value="">—</option>
              {SEWAGE.map((v) => <option key={v} value={v}>{tl(`sewageKind.${v}`)}</option>)}
            </Select>
          </Field>
          <Field label={t("parkingSpots")} htmlFor="parking_spots">
            <Input id="parking_spots" name="parking_spots" type="number" min={0} max={20} defaultValue={lv?.parking_spots ?? undefined} />
          </Field>
          <Field label={t("solarReady")} htmlFor="solar_ready">
            <Select id="solar_ready" name="solar_ready" defaultValue={triState(lv?.solar_ready)}>
              <option value="">—</option>
              <option value="yes">{t("yes")}</option>
              <option value="no">{t("no")}</option>
            </Select>
          </Field>
          <Field label={t("elevatorBackup")} htmlFor="elevator_backup">
            <Select id="elevator_backup" name="elevator_backup" defaultValue={triState(lv?.elevator_backup)}>
              <option value="">—</option>
              <option value="yes">{t("yes")}</option>
              <option value="no">{t("no")}</option>
            </Select>
          </Field>
          <Field label={tl("winter")} htmlFor="winter_comfort">
            <Select id="winter_comfort" name="winter_comfort" defaultValue={lv?.winter_comfort ?? ""}>
              <option value="">—</option>
              {WINTER.map((v) => <option key={v} value={v}>{tl(`winterComfort.${v}`)}</option>)}
            </Select>
          </Field>
          <Field label={tl("summer")} htmlFor="summer_comfort">
            <Select id="summer_comfort" name="summer_comfort" defaultValue={lv?.summer_comfort ?? ""}>
              <option value="">—</option>
              {SUMMER.map((v) => <option key={v} value={v}>{tl(`summerComfort.${v}`)}</option>)}
            </Select>
          </Field>
          <Field label={tl("highlights")} htmlFor="highlights" hint={t("onePerLine")}>
            <Textarea id="highlights" name="highlights" dir="auto" maxLength={700} defaultValue={(lv?.highlights ?? []).join("\n")} />
          </Field>
          <Field label={tl("thingsToKnow")} htmlFor="things_to_know" hint={t("onePerLine")}>
            <Textarea id="things_to_know" name="things_to_know" dir="auto" maxLength={700} defaultValue={(lv?.things_to_know ?? []).join("\n")} />
          </Field>
        </Card>

        <Card className="grid gap-4 p-4 sm:grid-cols-2">
          <Field label={t("titleEn")} htmlFor="title_en">
            <Input id="title_en" name="title_en" dir="ltr" maxLength={140} defaultValue={l?.title.en ?? ""} />
          </Field>
          <Field label={t("titleAr")} htmlFor="title_ar">
            <Input id="title_ar" name="title_ar" dir="rtl" maxLength={140} defaultValue={l?.title.ar ?? ""} />
          </Field>
          <Field label={t("descriptionEn")} htmlFor="description_en">
            <Textarea id="description_en" name="description_en" dir="ltr" maxLength={5000} defaultValue={l?.description.en ?? ""} />
          </Field>
          <Field label={t("descriptionAr")} htmlFor="description_ar">
            <Textarea id="description_ar" name="description_ar" dir="rtl" maxLength={5000} defaultValue={l?.description.ar ?? ""} />
          </Field>
          <Field label={t("whatsapp")} htmlFor="contact_whatsapp">
            <Input id="contact_whatsapp" name="contact_whatsapp" type="tel" dir="ltr" placeholder="+961 70 123 456" defaultValue={l?.contact_whatsapp ?? ""} />
          </Field>
        </Card>

        <Button type="submit" size="lg" disabled={busy} data-testid="save-listing">
          {listingId ? t("save") : t("createAndAddPhotos")}
        </Button>
      </form>
    </div>
  );
}
