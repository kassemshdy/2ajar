import { getLocale, getTranslations } from "next-intl/server";
import type { Location } from "@2ajar/contracts";
import { LocationOptions } from "./location-options";
import { Button } from "./ui/button";
import { Field, Input, Select } from "./ui/input";

export type SearchState = Partial<
  Record<
    "transaction_type" | "location" | "price_min" | "price_max" | "bedrooms_min" | "furnished" | "property_type" | "sort",
    string
  >
>;

const PROPERTY_TYPES = ["apartment", "studio", "duplex", "house", "villa", "chalet", "office", "shop", "land"];

export async function SearchFilters({
  locations,
  state,
  compact = false,
}: {
  locations: Location[];
  state: SearchState;
  compact?: boolean;
}) {
  const t = await getTranslations("filters");
  const te = await getTranslations("enums");
  const locale = await getLocale();
  const tx = state.transaction_type ?? "rent";

  return (
    <form
      action={`/${locale}/listings`}
      method="get"
      className="flex flex-col gap-4"
      role="search"
      data-testid="search-form"
    >
      <fieldset className="grid grid-cols-2 gap-1 rounded-lg bg-muted p-1">
        {(["rent", "sale"] as const).map((v) => (
          <label
            key={v}
            className="cursor-pointer rounded-md px-3 py-2 text-center text-sm font-medium has-[:checked]:bg-background has-[:checked]:shadow-sm"
          >
            <input type="radio" name="transaction_type" value={v} defaultChecked={tx === v} className="sr-only" />
            {t(v)}
          </label>
        ))}
      </fieldset>
      <div className={compact ? "grid gap-3 sm:grid-cols-2 lg:grid-cols-4" : "flex flex-col gap-3"}>
        <Field label={t("location")} htmlFor="f-location">
          <Select id="f-location" name="location" defaultValue={state.location ?? ""}>
            <option value="">{t("anyLocation")}</option>
            <LocationOptions locations={locations} locale={locale} />
          </Select>
        </Field>
        <Field label={t("priceMin")} htmlFor="f-pmin">
          <Input id="f-pmin" name="price_min" type="number" min={0} inputMode="numeric" defaultValue={state.price_min} />
        </Field>
        <Field label={t("priceMax")} htmlFor="f-pmax">
          <Input id="f-pmax" name="price_max" type="number" min={0} inputMode="numeric" defaultValue={state.price_max} />
        </Field>
        <Field label={t("bedrooms")} htmlFor="f-beds">
          <Select id="f-beds" name="bedrooms_min" defaultValue={state.bedrooms_min ?? ""}>
            <option value="">{t("any")}</option>
            {[1, 2, 3, 4].map((n) => (
              <option key={n} value={n}>
                {n}+
              </option>
            ))}
          </Select>
        </Field>
        {!compact ? (
          <>
            <Field label={t("furnished")} htmlFor="f-furn">
              <Select id="f-furn" name="furnished" defaultValue={state.furnished ?? ""}>
                <option value="">{t("any")}</option>
                {["furnished", "semi", "unfurnished"].map((v) => (
                  <option key={v} value={v}>
                    {te(v)}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("propertyType")} htmlFor="f-type">
              <Select id="f-type" name="property_type" defaultValue={state.property_type ?? ""}>
                <option value="">{t("any")}</option>
                {PROPERTY_TYPES.map((v) => (
                  <option key={v} value={v}>
                    {te(v)}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("sort")} htmlFor="f-sort">
              <Select id="f-sort" name="sort" defaultValue={state.sort ?? "newest"}>
                <option value="newest">{t("newest")}</option>
                <option value="price_asc">{t("priceAsc")}</option>
                <option value="price_desc">{t("priceDesc")}</option>
              </Select>
            </Field>
          </>
        ) : null}
      </div>
      <div className="flex gap-2">
        <Button type="submit" className="flex-1">
          {t("search")}
        </Button>
        {!compact ? (
          <a href={`/${locale}/listings`} className="inline-flex h-10 items-center px-3 text-sm text-muted-foreground">
            {t("reset")}
          </a>
        ) : null}
      </div>
    </form>
  );
}
