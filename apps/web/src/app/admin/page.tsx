"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { Alert, Badge, Button, Empty, ErrorBox, LoadingRows, PageHeader, Tabs, cx, input, td, th } from "@/components/ui";
import { api, errorText, patch, post, type AdminUser, type AuditEvent, type Page } from "@/lib/api";
import { useQueryState } from "@/lib/url";

function Users({ me }: { me: string | null }) {
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [resetLink, setResetLink] = useState<{ email: string; url: string } | null>(null);

  const load = useCallback(
    () =>
      api<Page<AdminUser>>("/admin/users?limit=100")
        .then((p) => setUsers(p.items))
        .catch((e) => setError(errorText(e))),
    [],
  );
  useEffect(() => {
    load();
  }, [load]);

  const act = (run: () => Promise<unknown>) => {
    setError(null);
    run()
      .then(load)
      .catch((e) => setError(errorText(e)));
  };

  if (!users) return error ? <ErrorBox message={error} /> : <LoadingRows label="Loading users" />;
  return (
    <div className="space-y-4">
      <ErrorBox message={error} />
      {resetLink && (
        <Alert tone="warning" title={`Reset link for ${resetLink.email}`}>
          <p>Hand it over through a channel you trust. It works once, for 30 minutes, and is not shown again.</p>
          <p className="measured mt-2 break-all text-ink">{resetLink.url}</p>
        </Alert>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr>
              <th className={th}>Email</th>
              <th className={th}>Role</th>
              <th className={th}>Status</th>
              <th className={cx(th, "max-lg:hidden")}>Created</th>
              <th className={th}>
                <span className="visually-hidden">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td className={cx(td, "[overflow-wrap:anywhere] text-ink")}>
                  {u.email}
                  {u.id === me && <span className="ml-2 text-muted">(you)</span>}
                  {u.sso && <span className="ml-2 text-muted">SSO</span>}
                </td>
                <td className={td}>
                  <select
                    aria-label={`Role of ${u.email}`}
                    className={cx(input, "w-auto")}
                    value={u.role}
                    onChange={(e) => act(() => patch(`/admin/users/${u.id}`, { role: e.target.value }))}
                  >
                    <option value="admin">Admin</option>
                    <option value="member">Member</option>
                  </select>
                </td>
                <td className={td}>
                  <Badge value={u.is_active ? "active" : "disabled"} tone={u.is_active ? "ok" : "neutral"} />
                </td>
                <td className={cx(td, "measured text-muted max-lg:hidden")}>{new Date(u.created_at).toLocaleString()}</td>
                <td className={cx(td, "text-right")}>
                  <div className="flex flex-wrap justify-end gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() =>
                        act(async () => {
                          const r = await post<{ url: string }>(`/admin/users/${u.id}/reset-link`);
                          setResetLink({ email: u.email, url: r.url });
                        })
                      }
                    >
                      Reset link
                    </Button>
                    <Button variant="secondary" size="sm" onClick={() => act(() => patch(`/admin/users/${u.id}`, { is_active: !u.is_active }))}>
                      {u.is_active ? "Disable" : "Enable"}
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const PAGE = 50;

function Audit() {
  const [page, setPage] = useState<Page<AuditEvent> | null>(null);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Page<AuditEvent>>(`/admin/audit?limit=${PAGE}&offset=${offset}`)
      .then(setPage)
      .catch((e) => setError(errorText(e)));
  }, [offset]);

  if (!page) return error ? <ErrorBox message={error} /> : <LoadingRows label="Loading audit log" />;
  if (!page.total) return <Empty>No events recorded yet.</Empty>;
  return (
    <div className="space-y-4">
      <ErrorBox message={error} />
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr>
              <th className={th}>When</th>
              <th className={th}>Who</th>
              <th className={th}>Action</th>
              <th className={cx(th, "max-lg:hidden")}>Request</th>
            </tr>
          </thead>
          <tbody>
            {page.items.map((e) => (
              <tr key={e.id}>
                <td className={cx(td, "measured whitespace-nowrap text-muted")}>{new Date(e.created_at).toLocaleString()}</td>
                <td className={cx(td, "[overflow-wrap:anywhere]")}>{e.actor_email ?? "Unknown"}</td>
                <td className={cx(td, "measured [overflow-wrap:anywhere]")}>
                  <span className="text-ink">{e.action}</span>
                  {e.resource_type && (
                    <span className="ml-2 text-muted">
                      {e.resource_type} {e.resource_id}
                    </span>
                  )}
                  {Object.keys(e.detail).length > 0 && <p className="mt-0.5 text-xs text-muted">{JSON.stringify(e.detail)}</p>}
                  <p className="mt-0.5 text-xs text-cool lg:hidden">{e.request_id}</p>
                </td>
                <td className={cx(td, "measured text-cool max-lg:hidden")}>{e.request_id}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between gap-4 text-sm text-muted">
        <p className="measured">
          {offset + 1} to {offset + page.items.length} of {page.total}
        </p>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
            Newer
          </Button>
          <Button variant="secondary" size="sm" disabled={offset + PAGE >= page.total} onClick={() => setOffset(offset + PAGE)}>
            Older
          </Button>
        </div>
      </div>
    </div>
  );
}

function AdminPage() {
  const [tab, setTab] = useQueryState("tab", "users");
  const [me, setMe] = useState<{ id: string; role: string } | null>(null);
  useEffect(() => {
    api<{ id: string; role: string }>("/auth/me").then(setMe).catch(() => undefined);
  }, []);

  return (
    <div className="space-y-6">
      <PageHeader title="Admin" description="Manage who can sign in, and review who changed what. Administrators do not see other accounts' documents or incidents." />
      {me && me.role !== "admin" ? (
        <Alert tone="warning">This page needs the administrator role.</Alert>
      ) : (
        <>
          <Tabs
            label="Admin sections"
            tabs={[
              { id: "users", label: "Users" },
              { id: "audit", label: "Audit log" },
            ]}
            value={tab === "audit" ? "audit" : "users"}
            onChange={setTab}
          />
          <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
            {tab === "audit" ? <Audit /> : <Users me={me?.id ?? null} />}
          </div>
        </>
      )}
    </div>
  );
}

export default function Page() {
  return (
    <Suspense>
      <AdminPage />
    </Suspense>
  );
}
