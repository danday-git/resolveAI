"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, useSyncExternalStore, type ReactNode } from "react";
import { api, post, providerNames, type Me } from "@/lib/api";
import { Icon, type IconName } from "./icons";
import { Alert, btn, cx, link } from "./ui";

const links: [string, string, IconName][] = [
  ["/", "Overview", "home"],
  ["/knowledge", "Knowledge Base", "book"],
  ["/assistant", "Assistant", "chat"],
  ["/incidents", "Incidents", "alert"],
  ["/metrics", "Evaluation / Ops", "chart"],
];

function Brand({ onClick }: { onClick?: () => void }) {
  return (
    <Link href="/" onClick={onClick} className="flex h-9 items-center text-lg font-medium tracking-[var(--tracking-display)] text-ink no-underline">
      ResolveAI
    </Link>
  );
}

const onThemeChange = (cb: () => void) => {
  window.addEventListener("themechange", cb);
  return () => window.removeEventListener("themechange", cb);
};

/** Graphite is the default; "paper" is the light colourway in tokens.css. The inline script in layout.tsx applies the stored choice before first paint. */
export function ThemeToggle({ className }: { className?: string }) {
  const light = useSyncExternalStore(
    onThemeChange,
    () => document.documentElement.dataset.theme === "paper",
    () => false,
  );
  return (
    <button
      className={cx(btn("ghost", "sm"), className)}
      onClick={() => {
        if (light) delete document.documentElement.dataset.theme;
        else document.documentElement.dataset.theme = "paper";
        try {
          localStorage.setItem("theme", light ? "graphite" : "paper");
        } catch {
          // Storage can be blocked; the switch still works for this page view.
        }
        window.dispatchEvent(new Event("themechange"));
      }}
    >
      {light ? "Dark mode" : "Light mode"}
    </button>
  );
}

function NavLinks({ path, admin, onNavigate }: { path: string; admin: boolean; onNavigate?: () => void }) {
  return (
    <ul className="flex flex-col gap-0.5">
      {(admin ? [...links, ["/admin", "Admin", "shield"] as const] : links).map(([href, label, icon]) => {
        const active = href === "/" ? path === "/" : path.startsWith(href);
        return (
          <li key={href}>
            <Link
              href={href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={cx(
                "flex h-11 items-center gap-2.5 whitespace-nowrap rounded-pill px-3 text-sm no-underline transition-colors duration-[var(--dur-micro)] active:bg-rule nav:h-9",
                active ? "bg-rule/60 text-ink" : "text-muted hover:text-ink",
              )}
            >
              <Icon name={icon} />
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
  const [me, setMe] = useState<Me | null>(null);
  const [drawer, setDrawer] = useState(false);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const wasDrawerOpen = useRef(false);
  const isLogin = ["/login", "/register", "/reset"].includes(path);

  useEffect(() => {
    if (isLogin) return;
    // Refetched on every navigation so the consent notice clears once it is given.
    api<Me>("/auth/me")
      .then(setMe)
      .catch(() => router.replace("/login"));
  }, [isLogin, router, path]);

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
    <div className="border-t border-rule pt-3">
      <Link
        href="/account"
        onClick={() => setDrawer(false)}
        aria-current={path === "/account" ? "page" : undefined}
        title={me ? `Account: ${me.email}` : undefined}
        className="measured block truncate rounded-pill px-3 py-1 text-muted no-underline transition-colors hover:text-ink active:bg-rule aria-[current]:text-ink"
      >
        {me?.email ?? "…"}
      </Link>
      <div className="mt-1 flex items-center justify-between gap-2">
        <ThemeToggle />
        <button className={btn("ghost", "sm")} onClick={signOut}>
          Sign out
        </button>
      </div>
    </div>
  );

  return (
    <div className="min-h-dvh nav:grid nav:grid-cols-[15rem_minmax(0,1fr)]">
      <a href="#main" inert={drawer} className="visually-hidden focus:fixed focus:left-2 focus:top-2 focus:z-[var(--z-tooltip)] focus:h-auto focus:w-auto focus:rounded-pill focus:bg-paper-3 focus:px-3 focus:py-2 focus:[clip-path:none]">
        Skip to content
      </a>
      <aside className="top-0 hidden h-dvh flex-col border-r border-rule px-3 py-4 nav:sticky nav:flex">
        <div className="px-3">
          <Brand />
        </div>
        <nav aria-label="Main" className="mt-6 flex-1 overflow-y-auto">
          <NavLinks path={path} admin={me?.role === "admin"} />
        </nav>
        {account}
      </aside>
      <header className="sticky top-0 z-[var(--z-sticky-nav)] border-b border-rule bg-paper nav:static nav:hidden">
        <div inert={drawer} className="flex h-14 items-center justify-between px-[var(--gutter)]">
          <Brand />
          <button ref={menuButtonRef} className={btn("ghost", "sm")} onClick={() => setDrawer(true)} aria-label="Open navigation" aria-expanded={drawer}>
            <Icon name="menu" className="h-5 w-5" />
          </button>
        </div>
        {drawer && (
          <div
            className="absolute inset-x-0 top-0 max-h-dvh overflow-y-auto border-b border-rule-2 bg-paper-2 px-[var(--gutter)] pb-4"
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
            <nav aria-label="Main" className="-mx-3 mb-3">
              <NavLinks path={path} admin={me?.role === "admin"} onNavigate={() => setDrawer(false)} />
            </nav>
            <div className="-mx-3">{account}</div>
          </div>
        )}
      </header>
      {drawer && <div className="fixed inset-0 z-[var(--z-sticky)] bg-scrim nav:hidden" onClick={() => setDrawer(false)} />}
      <main id="main" inert={drawer} className="mx-auto w-full max-w-[var(--container)] px-[var(--gutter)] pb-24 pt-10">
        {me?.llm_consent_required && path !== "/account" && (
          <div className="mb-6">
            <Alert tone="warning" title="Uploads, the assistant and incident analysis are paused for your account">
              They send your data to {providerNames(me.external_llm_providers)}.{" "}
              <Link href="/account" className={link}>
                Review and allow it on the Account page
              </Link>
              .
            </Alert>
          </div>
        )}
        {children}
      </main>
    </div>
  );
}
