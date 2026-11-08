"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api-client";
import { useSession } from "@/lib/session";

type FavoritesValue = {
  isSaved: (listingId: string) => boolean;
  /** Saves or un-saves; sends signed-out visitors to the login page. Returns the new state. */
  toggle: (listingId: string) => Promise<boolean>;
};

const FavoritesContext = createContext<FavoritesValue | null>(null);

/** The signed-in user's saved listing ids, loaded once and updated optimistically (the hearts). */
export function FavoritesProvider({ children }: { children: React.ReactNode }) {
  const { user } = useSession();
  const router = useRouter();
  const [ids, setIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!user) {
      setIds(new Set());
      return;
    }
    api<{ listing_ids: string[] }>("/me/favorites/ids")
      .then((r) => setIds(new Set(r.listing_ids)))
      .catch(() => setIds(new Set()));
  }, [user]);

  const toggle = useCallback(
    async (listingId: string) => {
      if (!user) {
        router.push("/login");
        return false;
      }
      const saved = ids.has(listingId);
      const next = new Set(ids);
      if (saved) next.delete(listingId);
      else next.add(listingId);
      setIds(next);
      try {
        await api(`/me/favorites/${listingId}`, { method: saved ? "DELETE" : "PUT" });
        return !saved;
      } catch {
        setIds(ids); // roll back
        return saved;
      }
    },
    [ids, router, user],
  );

  const value = useMemo<FavoritesValue>(() => ({ isSaved: (id) => ids.has(id), toggle }), [ids, toggle]);
  return <FavoritesContext.Provider value={value}>{children}</FavoritesContext.Provider>;
}

export function useFavorites(): FavoritesValue {
  const ctx = useContext(FavoritesContext);
  // Outside the provider (isolated tests, error pages) hearts render as "not saved" and do nothing.
  return ctx ?? { isSaved: () => false, toggle: async () => false };
}
