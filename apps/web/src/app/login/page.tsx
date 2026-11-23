"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Icon } from "@/components/icons";
import { Alert, Button, Field, input } from "@/components/ui";
import { errorText, post } from "@/lib/api";

const points: [string, string][] = [
  ["Grounded answers", "Every answer cites the exact SOP excerpt, or abstains."],
  ["Structured triage", "Observations, suspected causes and read-only checks, kept separate."],
  ["Human-confirmed RCA", "Drafts stay unconfirmed until a reviewer signs off."],
];

function LoginForm() {
  const router = useRouter();
  const expired = useSearchParams().get("expired");
  const [email, setEmail] = useState("demo@resolveai.local");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  return (
    <div className="grid min-h-dvh lg:grid-cols-[1fr_minmax(420px,1fr)]">
      <div className="hidden flex-col justify-between bg-zinc-950 p-10 text-zinc-100 lg:flex">
        <div className="flex items-center gap-2 font-semibold">
          <span className="grid h-7 w-7 place-items-center rounded-md bg-indigo-600">
            <Icon name="shield" className="h-4 w-4" />
          </span>
          ResolveAI
        </div>
        <div className="max-w-md space-y-8">
          <h2 className="text-3xl font-semibold tracking-tight">Investigate incidents with evidence, not guesses.</h2>
          <ul className="space-y-5">
            {points.map(([t, d]) => (
              <li key={t} className="flex gap-3">
                <span className="mt-0.5 grid h-6 w-6 place-items-center rounded-full bg-indigo-500/20 text-indigo-300">
                  <Icon name="check" className="h-3.5 w-3.5" />
                </span>
                <div>
                  <p className="font-medium">{t}</p>
                  <p className="text-sm text-zinc-400">{d}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
        <p className="text-xs text-zinc-500">Portfolio demo · synthetic data only</p>
      </div>
      <div className="flex items-center justify-center px-4 py-12">
        <form
          className="w-full max-w-sm space-y-5"
          noValidate={false}
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
          <div className="space-y-1">
            <div className="mb-6 flex items-center gap-2 font-semibold lg:hidden">
              <span className="grid h-7 w-7 place-items-center rounded-md bg-indigo-600 text-white">
                <Icon name="shield" className="h-4 w-4" />
              </span>
              ResolveAI
            </div>
            <h1 className="text-2xl font-semibold tracking-tight">Sign in</h1>
            <p className="text-sm text-zinc-500">
              Local demo authentication. Credentials come from <code className="font-mono text-xs">DEMO_USER_EMAIL</code> /{" "}
              <code className="font-mono text-xs">DEMO_USER_PASSWORD</code> (see README).
            </p>
          </div>
          {expired && !error && <Alert tone="warning">Your session expired. Please sign in again.</Alert>}
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
                  className="absolute inset-y-0 right-0 grid w-10 place-items-center rounded-r-control text-zinc-500 hover:text-zinc-800"
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
        </form>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
