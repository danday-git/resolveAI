"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthShell } from "@/components/AuthShell";
import { Button, ErrorBox, Field, input } from "@/components/ui";
import { errorText, post } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  return (
    <AuthShell title="Create account" description="New accounts are members: each sees only its own documents, incidents and usage.">
      <form
        className="space-y-5"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError(null);
          try {
            await post("/auth/register", { email, password });
            router.replace("/");
          } catch (err) {
            setError(errorText(err));
            setBusy(false);
          }
        }}
      >
        <ErrorBox message={error} />
        <Field label="Email">
          {(p) => <input {...p} className={input} type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="username" />}
        </Field>
        <Field label="Password" hint="12 to 72 characters.">
          {(p) => (
            <input {...p} className={input} type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={12} maxLength={72} autoComplete="new-password" />
          )}
        </Field>
        <Button type="submit" className="w-full" loading={busy}>
          {busy ? "Creating account…" : "Create account"}
        </Button>
      </form>
    </AuthShell>
  );
}
