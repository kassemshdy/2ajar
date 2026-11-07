"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { Permission, User } from "@2ajar/contracts";
import { usePathname } from "@/i18n/navigation";
import { api } from "@/lib/api-client";

type SessionValue = {
  /** undefined while loading, null when signed out */
  user: User | null | undefined;
  refresh: () => Promise<void>;
  signOut: () => Promise<void>;
  can: (permission: Permission) => boolean;
};

const SessionContext = createContext<SessionValue | null>(null);

/** Fetches the signed-in user once per navigation and shares it (header, bug button, admin pages). */
export function SessionProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [user, setUser] = useState<User | null | undefined>(undefined);

  const refresh = useCallback(async () => {
    try {
      setUser(await api<User>("/me"));
    } catch {
      setUser(null);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [pathname, refresh]);

  const signOut = useCallback(async () => {
    await api("/auth/logout", { method: "POST" }).catch(() => undefined);
    setUser(null);
  }, []);

  const value = useMemo<SessionValue>(
    () => ({
      user,
      refresh,
      signOut,
      can: (permission) => Boolean(user?.permissions?.includes(permission)),
    }),
    [user, refresh, signOut],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside <SessionProvider>");
  return ctx;
}
