"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Icon } from "@/components/icons";
import { ThemeToggle } from "@/components/Nav";
import { Alert, Button, Field, btn, cx, input, link } from "@/components/ui";
import { api, errorText, post } from "@/lib/api";

const points: [string, string][] = [
  ["Grounded answers", "Every answer cites the exact SOP excerpt, or abstains."],
  ["Structured triage", "Observations, suspected causes and read-only checks, kept separate."],
  ["Human-confirmed RCA", "Drafts stay unconfirmed until a reviewer signs off."],
];

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const expired = params.get("expired");
  const ssoFailed = params.get("reason") === "sso";
  const [email, setEmail] = useState("demo@resolveai.local");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [config, setConfig] = useState({ registration: false, oidc: false });
  useEffect(() => {
    api<typeof config>("/auth/config").then(setConfig).catch(() => undefined);
  }, []);

  return (
    <main className="mx-auto grid min-h-dvh max-w-[72rem] content-center gap-x-24 gap-y-16 px-[var(--gutter)] py-16 nav:grid-cols-[minmax(0,24rem)_minmax(0,1fr)]">
      <div className="space-y-8">
        <div className="flex items-center justify-between">
          <p className="text-lg font-medium tracking-[var(--tracking-display)]">ResolveAI</p>
          <ThemeToggle />
        </div>
        <form
          className="space-y-5"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError(null);
            try {
              await post("/auth/login", { email, password });
              router.replace("/");
            } catch (err) {
              setError(errorText(err));
              setBusy(false);
            }
          }}
        >
          <div className="space-y-3">
            <h1>Sign in</h1>
            <p className="text-sm text-muted">
              Use the account your administrator gave you. On a demo install, the demo account is filled in and its password is in the README.
            </p>
          </div>
          {expired && !error && <Alert tone="warning">Your session expired. Please sign in again.</Alert>}
          {ssoFailed && !error && (
            <Alert tone="danger">Single sign-on did not complete. The identity provider must return a verified email for an active account.</Alert>
          )}
          {error && <Alert tone="danger">{error}</Alert>}
          <Field label="Email">
            {(p) => <input {...p} className={input} type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="username" />}
          </Field>
          <Field label="Password">
            {(p) => (
              <div className="relative">
                <input
                  {...p}
                  className={`${input} pr-10`}
                  type={show ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShow((s) => !s)}
                  className="absolute inset-y-0 right-0 grid w-10 place-items-center rounded-r-pill text-muted transition-colors hover:text-ink active:text-accent"
                  aria-label={show ? "Hide password" : "Show password"}
                  aria-pressed={show}
                >
                  <Icon name={show ? "eyeOff" : "eye"} />
                </button>
              </div>
            )}
          </Field>
          <Button type="submit" className="w-full" loading={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </Button>
          {config.oidc && (
            // A full navigation: the API redirects the browser to the identity provider.
            <a href="/api/v1/auth/oidc/login" className={cx(btn("secondary"), "w-full no-underline")}>
              Sign in with single sign-on
            </a>
          )}
          <p className="flex flex-wrap justify-between gap-x-6 gap-y-2 text-sm">
            <Link href="/reset" className={link}>
              Forgot password?
            </Link>
            {config.registration && (
              <Link href="/register" className={link}>
                Create account
              </Link>
            )}
          </p>
        </form>
      </div>
      <section className="self-center">
        <h2 className="text-display-s">Investigate incidents with evidence, not guesses.</h2>
        <dl className="mt-8 border-t border-rule">
          {points.map(([t, d]) => (
            <div key={t} className="grid gap-x-6 gap-y-1 border-b border-rule py-4 sm:grid-cols-[12rem_1fr]">
              <dt className="text-ink">{t}</dt>
              <dd className="text-sm text-muted">{d}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-6 text-sm text-muted">Portfolio demo with synthetic data only.</p>
      </section>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
