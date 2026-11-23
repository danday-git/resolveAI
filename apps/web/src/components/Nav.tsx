"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, post } from "@/lib/api";

const links = [
  ["/", "Overview"],
  ["/knowledge", "Knowledge Base"],
  ["/assistant", "Assistant"],
  ["/incidents", "Incidents"],
  ["/metrics", "Evaluation / Ops"],
] as const;

export function Nav() {
  const path = usePathname();
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    if (path === "/login") return;
    api<{ email: string }>("/auth/me")
      .then((u) => setEmail(u.email))
      .catch(() => router.replace("/login"));
  }, [path, router]);

  if (path === "/login") return null;
  return (
    <header className="border-b border-slate-200 bg-white">
      <nav className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
        <span className="mr-2 font-bold text-slate-900">ResolveAI</span>
        {links.map(([href, label]) => {
          const active = href === "/" ? path === "/" : path.startsWith(href);
          return (
            <Link key={href} href={href} className={`text-sm ${active ? "font-semibold text-slate-900" : "text-slate-600 hover:text-slate-900"}`}>
              {label}
            </Link>
          );
        })}
        <span className="ml-auto text-xs text-slate-500">{email}</span>
        <button
          className="text-xs text-slate-600 underline"
          onClick={async () => {
            await post("/auth/logout").catch(() => undefined);
            router.replace("/login");
          }}
        >
          Sign out
        </button>
      </nav>
    </header>
  );
}
