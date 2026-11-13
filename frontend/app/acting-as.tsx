"use client";

// There's no login. You pick who you're acting as, it's remembered in this
// browser, and every API call sends it in the X-Acting-As header.

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, type Person } from "@/lib/api";
import { ROLE_LABEL } from "@/lib/labels";

type ActingAs = {
  people: Person[];
  me: Person | null;
  setMe: (id: string) => void;
  nameOf: (id: string | null) => string;
  error: string | null;
};

const Context = createContext<ActingAs | null>(null);
const STORAGE_KEY = "serviceops.actingAs";

export function ActingAsProvider({ children }: { children: React.ReactNode }) {
  const [people, setPeople] = useState<Person[]>([]);
  const [meId, setMeId] = useState("asha");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (saved) setMeId(saved);
    } catch {
      // Storage can be blocked; the default person is fine.
    }
    api<Person[]>("/api/people").then(setPeople, (e: Error) => setError(e.message));
  }, []);

  const setMe = useCallback((id: string) => {
    setMeId(id);
    try {
      window.localStorage.setItem(STORAGE_KEY, id);
    } catch {
      // Not remembered, but still works for this page.
    }
  }, []);

  const nameOf = useCallback(
    (id: string | null) => (id ? people.find((p) => p.id === id)?.name ?? id : ""),
    [people],
  );

  const me = people.find((p) => p.id === meId) ?? null;
  return <Context.Provider value={{ people, me, setMe, nameOf, error }}>{children}</Context.Provider>;
}

export function useActingAs(): ActingAs {
  const value = useContext(Context);
  if (!value) throw new Error("useActingAs must be used inside ActingAsProvider");
  return value;
}

export function ActingAsPicker() {
  const { people, me, setMe } = useActingAs();
  return (
    <label className="acting-as">
      Acting as
      <select value={me?.id ?? ""} onChange={(e) => setMe(e.target.value)} disabled={people.length === 0}>
        {people.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name} ({ROLE_LABEL[p.role]})
          </option>
        ))}
      </select>
    </label>
  );
}

export function ApiStatus() {
  const { error } = useActingAs();
  return error ? (
    <p className="banner error" role="alert">
      {error}
    </p>
  ) : null;
}
