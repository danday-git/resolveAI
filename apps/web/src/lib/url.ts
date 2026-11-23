"use client";

import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

/** State mirrored into the query string so a filter or tab survives reload and can be shared. Needs a Suspense boundary above. */
export function useQueryState(key: string, fallback = ""): [string, (v: string) => void] {
  const param = useSearchParams().get(key) ?? fallback;
  const [value, setValue] = useState(param);
  const [seen, setSeen] = useState(param);
  const [sent, setSent] = useState<string[]>([]); // our own writes the router has not echoed back yet
  if (param !== seen) {
    setSeen(param);
    const echo = sent.lastIndexOf(param);
    setSent(sent.slice(echo + 1));
    // Anything else is a navigation that changed the query (e.g. the nav link to this same page): follow it.
    if (echo < 0) setValue(param);
  }
  // Stable identity, so effects that call the setter do not re-run on every render.
  const set = useCallback(
    (v: string) => {
      setValue(v);
      setSent((xs) => [...xs, v]);
      const url = new URL(window.location.href);
      if (v === fallback) url.searchParams.delete(key);
      else url.searchParams.set(key, v);
      window.history.replaceState(null, "", url);
    },
    [key, fallback],
  );
  return [value, set];
}

/** The value once it has stopped changing, so typing in a search box sends one request, not one per key. */
export function useDebounced<T>(value: T, ms = 250): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return settled;
}

export const PAGE_SIZE = 25;
/** 1-based page number from its URL value. */
export const pageNumber = (value: string) => Math.max(1, Math.floor(Number(value)) || 1);
