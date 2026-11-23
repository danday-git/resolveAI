"use client";

import { useSearchParams } from "next/navigation";
import { useState } from "react";

/** State mirrored into the query string so a filter or tab survives reload and can be shared. Needs a Suspense boundary above. */
export function useQueryState(key: string, fallback = ""): [string, (v: string) => void] {
  const param = useSearchParams().get(key) ?? fallback;
  const [value, setValue] = useState(param);
  const [seen, setSeen] = useState(param);
  if (param !== seen) {
    setSeen(param);
    // Follow a navigation that changed the query (e.g. the nav link to this same page), but not the late echo of an older write of ours.
    if ((new URL(window.location.href).searchParams.get(key) ?? fallback) === param) setValue(param);
  }
  return [
    value,
    (v) => {
      setValue(v);
      const url = new URL(window.location.href);
      if (v === fallback) url.searchParams.delete(key);
      else url.searchParams.set(key, v);
      window.history.replaceState(null, "", url);
    },
  ];
}
