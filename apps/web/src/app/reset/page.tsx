"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { AuthShell } from "@/components/AuthShell";
import { Alert, Button, ErrorBox, Field, input } from "@/components/ui";
import { errorText, post } from "@/lib/api";

function ResetForm() {
  const token = useSearchParams().get("token");
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (token) await post("/auth/password-reset/confirm", { token, new_password: value });
      else await post("/auth/password-reset/request", { email: value });
      setDone(true);
    } catch (err) {
      setError(errorText(err));
    }
    setBusy(false);
  }

  if (done)
    return (
      <AuthShell title={token ? "Password changed" : "Check your email"}>
        <Alert tone="success">
          {token
            ? "Your new password is set and every earlier session is signed out."
            : "If that address has an account and this server can send email, a reset link is on its way. It works once, for 30 minutes. No email? Ask an administrator for a reset link."}
        </Alert>
      </AuthShell>
    );

  return (
    <AuthShell
      title={token ? "Choose a new password" : "Reset password"}
      description={token ? "This link works once." : "Enter the email you sign in with."}
    >
      <form className="space-y-5" onSubmit={submit}>
        <ErrorBox message={error} />
        {token ? (
          <Field label="New password" hint="12 to 72 characters.">
            {(p) => (
              <input {...p} className={input} type="password" value={value} onChange={(e) => setValue(e.target.value)} required minLength={12} maxLength={72} autoComplete="new-password" />
            )}
          </Field>
        ) : (
          <Field label="Email">
            {(p) => <input {...p} className={input} type="email" value={value} onChange={(e) => setValue(e.target.value)} required autoComplete="username" />}
          </Field>
        )}
        <Button type="submit" className="w-full" loading={busy}>
          {token ? "Set password" : "Send reset link"}
        </Button>
      </form>
    </AuthShell>
  );
}

export default function ResetPage() {
  return (
    <Suspense>
      <ResetForm />
    </Suspense>
  );
}
