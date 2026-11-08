"use client";

import { Heart } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import type { ListingPublic } from "@2ajar/contracts";
import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api-client";
import { useFavorites } from "@/lib/favorites";
import { useSession } from "@/lib/session";
import { ListingTile } from "./listing-tile";
import { buttonVariants } from "./ui/button";

/** The signed-in user's saved homes ("wishlist"). Un-hearting a home removes it from the grid at once. */
export function SavedListings() {
  const t = useTranslations("saved");
  const { user } = useSession();
  const { isSaved } = useFavorites();
  const [items, setItems] = useState<ListingPublic[] | null>(null);

  useEffect(() => {
    if (!user) return;
    api<ListingPublic[]>("/me/favorites")
      .then(setItems)
      .catch(() => setItems([]));
  }, [user]);

  if (user === undefined) return null;
  if (user === null) {
    return (
      <div className="flex flex-col items-start gap-3">
        <p className="text-muted-foreground">{t("loginToSave")}</p>
        <Link href="/login" className={buttonVariants()}>
          {t("loginToSave")}
        </Link>
      </div>
    );
  }
  if (items === null) return null;
  const visible = items.filter((x) => isSaved(x.id));

  if (!visible.length) {
    return (
      <div className="flex flex-col items-start gap-3 py-6" data-testid="saved-empty">
        <Heart className="size-8 text-muted-foreground" aria-hidden />
        <p className="text-muted-foreground">{t("empty")}</p>
        <Link href="/" className={buttonVariants({ variant: "outline" })}>
          {t("explore")}
        </Link>
      </div>
    );
  }
  return (
    <ul className="grid grid-cols-1 gap-x-5 gap-y-8 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4" data-testid="saved-grid">
      {visible.map((l) => (
        <li key={l.id}>
          <ListingTile listing={l} />
        </li>
      ))}
    </ul>
  );
}
