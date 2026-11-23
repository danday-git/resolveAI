"use client";

import { useSearchParams } from "next/navigation";
import { useState } from "react";

/** State mirrored into the query string so a filter or tab survives reload and can be shared. Needs a Suspense boundary above. */
export function useQueryState(key: string, fallback = ""): [string, (v: string) => void] {
  const [value, setValue] = useState(useSearchParams().get(key) ?? fallback);
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
