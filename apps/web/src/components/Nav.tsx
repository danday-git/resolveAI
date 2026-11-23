"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { api, post } from "@/lib/api";
import { Icon } from "./icons";
import { btn, cx } from "./ui";

const links: [string, string][] = [
  ["/", "Overview"],
  ["/knowledge", "Knowledge Base"],
  ["/assistant", "Assistant"],
  ["/incidents", "Incidents"],
  ["/metrics", "Evaluation / Ops"],
];

function Brand({ onClick }: { onClick?: () => void }) {
  return (
    <Link href="/" onClick={onClick} className="flex h-9 items-center text-lg font-medium tracking-[var(--tracking-display)] text-ink no-underline">
      ResolveAI
    </Link>
  );
}

function NavLinks({ path, onNavigate, stacked }: { path: string; onNavigate?: () => void; stacked?: boolean }) {
  return (
    <ul className={stacked ? "flex flex-col" : "flex items-center gap-1"}>
      {links.map(([href, label]) => {
        const active = href === "/" ? path === "/" : path.startsWith(href);
        return (
          <li key={href}>
            <Link
              href={href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={cx(
                "flex items-center whitespace-nowrap rounded-pill px-3 text-sm no-underline transition-colors duration-[var(--dur-micro)] active:bg-rule",
                stacked ? "h-11" : "h-9",
                active ? "bg-paper-2 text-ink" : "text-muted hover:text-ink",
              )}
            >
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
    const mq = window.matchMedia("(min-width: 60rem)");
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
  const account = (
    <>
      <span className="measured min-w-0 truncate text-muted" title={email ?? undefined}>
        {email ?? "…"}
      </span>
      <button className={btn("ghost", "sm")} onClick={signOut}>
        Sign out
      </button>
    </>
  );

  return (
    <div className="min-h-dvh">
      <a href="#main" inert={drawer} className="visually-hidden focus:fixed focus:left-2 focus:top-2 focus:z-[var(--z-tooltip)] focus:h-auto focus:w-auto focus:rounded-pill focus:bg-paper-3 focus:px-3 focus:py-2 focus:[clip-path:none]">
        Skip to content
      </a>
      <header className="sticky top-0 z-[var(--z-sticky-nav)] border-b border-rule bg-paper">
        <div inert={drawer} className="mx-auto flex h-14 max-w-[var(--container)] items-center gap-6 px-[var(--gutter)]">
          <Brand />
          <nav aria-label="Main" className="hidden min-w-0 flex-1 nav:block">
            <NavLinks path={path} />
          </nav>
          <div className="hidden min-w-0 items-center gap-2 nav:flex">{account}</div>
          <button
            ref={menuButtonRef}
            className={cx(btn("ghost", "sm"), "ml-auto nav:hidden")}
            onClick={() => setDrawer(true)}
            aria-label="Open navigation"
            aria-expanded={drawer}
          >
            <Icon name="menu" className="h-5 w-5" />
          </button>
        </div>
        {drawer && (
          <div
            className="absolute inset-x-0 top-0 border-b border-rule-2 bg-paper-2 px-[var(--gutter)] pb-4 nav:hidden"
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
            <div className="flex h-14 items-center justify-between">
              <Brand onClick={() => setDrawer(false)} />
              <button autoFocus className={btn("ghost", "sm")} onClick={() => setDrawer(false)} aria-label="Close navigation">
                <Icon name="x" className="h-5 w-5" />
              </button>
            </div>
            <nav aria-label="Main" className="-mx-3">
              <NavLinks path={path} onNavigate={() => setDrawer(false)} stacked />
            </nav>
            <div className="mt-3 flex items-center justify-between gap-3 border-t border-rule pt-3">{account}</div>
          </div>
        )}
      </header>
      {drawer && <div className="fixed inset-0 z-[var(--z-sticky)] bg-scrim nav:hidden" onClick={() => setDrawer(false)} />}
      <main id="main" inert={drawer} className="mx-auto max-w-[var(--container)] px-[var(--gutter)] pb-24 pt-10">
        {children}
      </main>
    </div>
  );
}
