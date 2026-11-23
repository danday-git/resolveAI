"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { api, post } from "@/lib/api";
import { Icon, type IconName } from "./icons";
import { btn, cx } from "./ui";

const links: [string, string, IconName][] = [
  ["/", "Overview", "home"],
  ["/knowledge", "Knowledge Base", "book"],
  ["/assistant", "Assistant", "chat"],
  ["/incidents", "Incidents", "alert"],
  ["/metrics", "Evaluation / Ops", "chart"],
];

function Brand({ onClick }: { onClick?: () => void }) {
  return (
    <Link href="/" onClick={onClick} className="flex items-center gap-2 font-semibold tracking-tight text-zinc-950">
      <span className="grid h-7 w-7 place-items-center rounded-md bg-indigo-600 text-white">
        <Icon name="shield" className="h-4 w-4" />
      </span>
      ResolveAI
    </Link>
  );
}

function NavLinks({ path, onNavigate }: { path: string; onNavigate?: () => void }) {
  return (
    <ul className="space-y-0.5">
      {links.map(([href, label, icon]) => {
        const active = href === "/" ? path === "/" : path.startsWith(href);
        return (
          <li key={href}>
            <Link
              href={href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={cx(
                "flex items-center gap-2.5 rounded-control px-2.5 py-2 text-sm font-medium transition-colors",
                active ? "bg-white text-zinc-950 shadow-xs ring-1 ring-zinc-200" : "text-zinc-600 hover:bg-zinc-200/60 hover:text-zinc-900",
              )}
            >
              <Icon name={icon} className={cx("h-4 w-4", active ? "text-indigo-600" : "text-zinc-400")} />
              {label}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);
  const [drawer, setDrawer] = useState(false);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const wasDrawerOpen = useRef(false);
  const isLogin = path === "/login";

  useEffect(() => {
    if (isLogin) return;
    api<{ email: string }>("/auth/me")
      .then((u) => setEmail(u.email))
      .catch(() => router.replace("/login"));
  }, [isLogin, router]);

  useEffect(() => {
    if (!drawer) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setDrawer(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawer]);

  useEffect(() => {
    if (!drawer) return;
    const mq = window.matchMedia("(min-width: 1024px)");
    const onChange = () => {
      if (mq.matches) setDrawer(false);
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [drawer]);

  useEffect(() => {
    if (wasDrawerOpen.current && !drawer) menuButtonRef.current?.focus();
    wasDrawerOpen.current = drawer;
  }, [drawer]);

  if (isLogin) return <>{children}</>;

  const signOut = async () => {
    await post("/auth/logout").catch(() => undefined);
    router.replace("/login");
  };
  const footer = (
    <div className="space-y-2 border-t border-zinc-200 pt-3">
      <p className="truncate px-2.5 text-xs text-zinc-500" title={email ?? undefined}>
        {email ?? "…"}
      </p>
      <button className={cx(btn("ghost", "sm"), "w-full justify-start")} onClick={signOut}>
        <Icon name="logout" /> Sign out
      </button>
    </div>
  );

  return (
    <div className="min-h-dvh lg:pl-60">
      <a href="#main" inert={drawer} className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2">
        Skip to content
      </a>
      <aside inert={drawer} className="fixed inset-y-0 left-0 hidden w-60 flex-col gap-6 border-r border-zinc-200 bg-zinc-100/70 px-3 py-4 lg:flex">
        <div className="px-2.5">
          <Brand />
        </div>
        <nav aria-label="Main" className="flex-1">
          <NavLinks path={path} />
        </nav>
        {footer}
      </aside>
      <header inert={drawer} className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-zinc-200 bg-white/90 px-4 backdrop-blur lg:hidden">
        <Brand />
        <button ref={menuButtonRef} className={btn("ghost", "sm")} onClick={() => setDrawer(true)} aria-label="Open navigation" aria-expanded={drawer}>
          <Icon name="menu" className="h-5 w-5" />
        </button>
      </header>
      {drawer && (
        <div
          className="fixed inset-0 z-40 lg:hidden"
          role="dialog"
          aria-modal="true"
          aria-label="Navigation"
          onKeyDown={(event) => {
            if (event.key !== "Tab") return;
            const focusable = event.currentTarget.querySelectorAll<HTMLElement>("a[href], button:not([disabled])");
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (event.shiftKey && document.activeElement === first) {
              event.preventDefault();
              last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
              event.preventDefault();
              first.focus();
            }
          }}
        >
          <div className="absolute inset-0 bg-zinc-950/40" onClick={() => setDrawer(false)} />
          <div className="absolute inset-y-0 left-0 flex w-72 max-w-[85vw] flex-col gap-6 bg-zinc-50 px-3 py-4 shadow-xl">
            <div className="flex items-center justify-between px-2.5">
              <Brand onClick={() => setDrawer(false)} />
              <button autoFocus className={btn("ghost", "sm")} onClick={() => setDrawer(false)} aria-label="Close navigation">
                <Icon name="x" />
              </button>
            </div>
            <nav aria-label="Main" className="flex-1">
              <NavLinks path={path} onNavigate={() => setDrawer(false)} />
            </nav>
            {footer}
          </div>
        </div>
      )}
      <main id="main" inert={drawer} className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        {children}
      </main>
    </div>
  );
}
