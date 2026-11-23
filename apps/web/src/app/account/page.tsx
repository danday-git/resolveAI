"use client";

import { useState } from "react";
import { Alert, Button, Card, ErrorBox, Field, PageHeader, input } from "@/components/ui";
import { errorText, post } from "@/lib/api";

export default function AccountPage() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  return (
    <div className="space-y-6">
      <PageHeader title="Account" description="Settings for the account you are signed in with." />
      <Card title="Change password" description="Changing it signs out every other session of this account.">
        <form
          className="max-w-sm space-y-5"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError(null);
            setDone(false);
            try {
              await post("/auth/password", { current_password: current, new_password: next });
              setCurrent("");
              setNext("");
              setDone(true);
            } catch (err) {
              setError(errorText(err));
            }
            setBusy(false);
          }}
        >
          <ErrorBox message={error} />
          {done && <Alert tone="success">Password changed.</Alert>}
          <Field label="Current password">
            {(p) => <input {...p} className={input} type="password" value={current} onChange={(e) => setCurrent(e.target.value)} required autoComplete="current-password" />}
          </Field>
          <Field label="New password" hint="12 to 72 characters.">
            {(p) => (
              <input {...p} className={input} type="password" value={next} onChange={(e) => setNext(e.target.value)} required minLength={12} maxLength={72} autoComplete="new-password" />
            )}
          </Field>
          <Button type="submit" loading={busy}>
            Change password
          </Button>
        </form>
      </Card>
    </div>
  );
}
