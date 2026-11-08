"use client";

import { LocateFixed, MapPin } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import type { ListingPublic } from "@2ajar/contracts";
import { api } from "@/lib/api-client";
import { ListingTile } from "../listing-tile";
import { Button } from "../ui/button";
import { Row } from "./row";

type Nearby = { listing: ListingPublic; distance_km: number };
type State = "idle" | "locating" | "denied" | "done";

/**
 * "Homes near you". Location is asked for only when the visitor clicks, used for one query and never stored.
 */
export function NearYou() {
  const t = useTranslations("discover");
  const tl = useTranslations("listing");
  const [state, setState] = useState<State>("idle");
  const [hits, setHits] = useState<Nearby[]>([]);

  function locate() {
    if (!("geolocation" in navigator)) {
      setState("denied");
      return;
    }
    setState("locating");
    navigator.geolocation.getCurrentPosition(
      async ({ coords }) => {
        try {
          const lat = coords.latitude.toFixed(4); // ~10 m: enough to rank homes, no more precise than needed
          const lng = coords.longitude.toFixed(4);
          setHits(await api<Nearby[]>(`/listings/nearby?lat=${lat}&lng=${lng}&limit=12`));
          setState("done");
        } catch {
          setState("denied");
        }
      },
      () => setState("denied"),
      { maximumAge: 600_000, timeout: 10_000 },
    );
  }

  if (state === "done" && hits.length) {
    return (
      <Row title={t("nearYou")} testId="row-near-you">
        {hits.map((h) => (
          <ListingTile key={h.listing.id} listing={h.listing} note={tl("kmAway", { km: h.distance_km })} />
        ))}
      </Row>
    );
  }

  return (
    <section
      className="flex flex-col items-start gap-3 rounded-2xl border border-border p-5 sm:flex-row sm:items-center sm:justify-between"
      data-testid="near-you"
    >
      <div className="flex items-start gap-3">
        <span className="rounded-full bg-primary/10 p-2.5 text-primary">
          <MapPin className="size-5" aria-hidden />
        </span>
        <div>
          <h2 className="font-semibold">{t("nearYou")}</h2>
          <p className="text-sm text-muted-foreground" role="status">
            {state === "denied" ? t("locationDenied") : state === "done" ? t("noneNearby") : t("nearYouHint")}
          </p>
        </div>
      </div>
      <Button type="button" variant="outline" onClick={locate} disabled={state === "locating"} className="gap-2">
        <LocateFixed className="size-4" aria-hidden />
        {state === "locating" ? t("locating") : t("useLocation")}
      </Button>
    </section>
  );
}
