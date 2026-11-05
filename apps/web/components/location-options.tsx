import type { Location } from "@2ajar/contracts";

/** <option>s for a location hierarchy, indented by depth. Values are slugs or ids. */
export function LocationOptions({
  locations,
  locale,
  valueKey = "slug",
}: {
  locations: Location[];
  locale: string;
  valueKey?: "slug" | "id";
}) {
  return (
    <>
      {locations.map((loc) => {
        const depth = loc.path.split("/").length - 1;
        const name = locale === "ar" ? loc.name_ar : loc.name_en;
        return (
          <option key={loc.id} value={loc[valueKey]}>
            {"  ".repeat(depth) + name}
          </option>
        );
      })}
    </>
  );
}
