"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { ErrorBox, button, input } from "@/components/ui";
import { errorText, post } from "@/lib/api";

function LoginForm() {
  const router = useRouter();
  const expired = useSearchParams().get("expired");
  const [email, setEmail] = useState("demo@resolveai.local");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(expired ? "Your session expired. Please sign in again." : null);
  const [busy, setBusy] = useState(false);

  return (
    <form
      className="mx-auto mt-16 max-w-sm space-y-4 rounded-lg border border-slate-200 bg-white p-6 shadow-sm"
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        setError(null);
        try {
          await post("/auth/login", { email, password });
          router.replace("/");
        } catch (err) {
          setError(errorText(err));
        } finally {
          setBusy(false);
        }
      }}
    >
      <h1 className="text-xl font-bold">Sign in to ResolveAI</h1>
      <p className="text-xs text-slate-500">
        Local demo authentication. Credentials come from DEMO_USER_EMAIL / DEMO_USER_PASSWORD (see README).
      </p>
      <label className="block text-sm">
        Email
        <input className={input} type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="username" />
      </label>
      <label className="block text-sm">
        Password
        <input className={input} type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" />
      </label>
      <ErrorBox message={error} />
      <button className={`${button} w-full`} disabled={busy}>
        {busy ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
