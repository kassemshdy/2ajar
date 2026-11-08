"use client";

import { Heart } from "lucide-react";
import { useTranslations } from "next-intl";
import { useFavorites } from "@/lib/favorites";
import { cn } from "@/lib/utils";

/** Airbnb-style heart. On images it floats over the photo; inline it shows a label. */
export function FavoriteButton({
  listingId,
  variant = "overlay",
}: {
  listingId: string;
  variant?: "overlay" | "inline";
}) {
  const t = useTranslations("listing");
  const { isSaved, toggle } = useFavorites();
  const saved = isSaved(listingId);

  return (
    <button
      type="button"
      aria-pressed={saved}
      aria-label={saved ? t("saved") : t("save")}
      data-testid="favorite-button"
      onClick={(e) => {
        // The heart sits inside a link card: saving must not open the listing.
        e.preventDefault();
        e.stopPropagation();
        void toggle(listingId);
      }}
      className={cn(
        "inline-flex items-center gap-1.5 transition active:scale-90",
        variant === "overlay"
          ? "rounded-full p-1.5 drop-shadow-md hover:scale-110"
          : "rounded-lg px-3 py-1.5 text-sm font-medium underline-offset-2 hover:bg-muted",
      )}
    >
      <Heart
        className={cn(
          "size-6",
          variant === "overlay" ? "stroke-white stroke-[2]" : "size-4",
          saved ? "fill-rose-500 stroke-rose-500" : variant === "overlay" ? "fill-black/40" : "",
        )}
        aria-hidden
      />
      {variant === "inline" ? <span>{saved ? t("saved") : t("save")}</span> : null}
    </button>
  );
}
