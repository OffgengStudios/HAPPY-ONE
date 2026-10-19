"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { LogOut, RefreshCw } from "lucide-react";
import { api, Me, Session, time } from "@/lib/api";
import { useState } from "react";

export function SecuritySettings({
  user,
  onRefresh,
}: {
  user: Me;
  onRefresh: () => Promise<unknown>;
}) {
  const client = useQueryClient();
  const sessions = useQuery({
    queryKey: ["sessions"],
    queryFn: () => api<Session[]>("/auth/sessions"),
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [secret, setSecret] = useState("");
  const [recovery, setRecovery] = useState<string[]>([]);
  async function enrol() {
    setBusy("mfa");
    setError("");
    try {
      const result = await api<{ secret: string }>("/auth/mfa/enrol", "POST", {
        password,
      });
      setSecret(result.secret);
      setPassword("");
    } catch (value) {
      setError(value instanceof Error ? value.message : "MFA setup failed.");
    } finally {
      setBusy("");
    }
  }
  async function confirm() {
    setBusy("mfa");
    setError("");
    try {
      const result = await api<{ recovery_codes: string[] }>(
        "/auth/mfa/confirm",
        "POST",
        { password, code },
      );
      setRecovery(result.recovery_codes);
      setSecret("");
      setPassword("");
      setCode("");
      await onRefresh();
    } catch (value) {
      setError(
        value instanceof Error ? value.message : "MFA confirmation failed.",
      );
    } finally {
      setBusy("");
    }
  }
  async function revoke(session: Session) {
    if (
      !window.confirm(
        session.current ? "Sign out this device?" : "Revoke this session?",
      )
    )
      return;
    setBusy(session.id);
    setError("");
    try {
      await api("/auth/sessions/" + session.id + "/revoke", "POST");
      await client.invalidateQueries({ queryKey: ["sessions"] });
      await onRefresh();
    } catch (error) {
      setError(error instanceof Error ? error.message : "Revocation failed.");
    } finally {
      setBusy("");
    }
  }
  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Account security</h2>
      <dl className="grid gap-4 border-y border-border py-5 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-muted">Email</dt>
          <dd className="mt-1 break-all">{user.email}</dd>
        </div>
        <div>
          <dt className="text-muted">Multi-factor authentication</dt>
          <dd className="mt-1">
            {user.mfa_enabled ? "Enabled" : "Not enabled"}
          </dd>
        </div>
      </dl>
      {!user.mfa_enabled && (
        <section className="space-y-4 border-b border-border pb-6">
          <h3 className="font-semibold">Authenticator app</h3>
          {!secret ? (
            <div className="flex flex-wrap items-end gap-3">
              <label className="field-label flex-1">
                Current password
                <input
                  className="field"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </label>
              <button
                className="command primary"
                disabled={!password || busy === "mfa"}
                onClick={() => void enrol()}
              >
                Set up MFA
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              <p className="text-sm">
                Add this setup key to your authenticator app:{" "}
                <strong className="break-all">{secret}</strong>
              </p>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="field-label">
                  Current password
                  <input
                    className="field"
                    type="password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                  />
                </label>
                <label className="field-label">
                  Six-digit code
                  <input
                    className="field"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    value={code}
                    onChange={(event) => setCode(event.target.value)}
                  />
                </label>
              </div>
              <button
                className="command primary"
                disabled={!password || !code || busy === "mfa"}
                onClick={() => void confirm()}
              >
                Confirm MFA
              </button>
            </div>
          )}
        </section>
      )}
      {recovery.length > 0 && (
        <section className="border-y border-border py-5">
          <h3 className="font-semibold">Recovery codes</h3>
          <p className="mt-1 text-sm text-muted">
            Store these once. Each code can be used for one sign-in.
          </p>
          <ul className="mt-3 grid grid-cols-2 gap-2 font-mono text-sm">
            {recovery.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      )}
      <div className="flex items-center justify-between">
        <h3 className="font-semibold">Active sessions</h3>
        <button
          className="icon-button"
          aria-label="Refresh sessions"
          title="Refresh sessions"
          onClick={() => void sessions.refetch()}
        >
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>
      {error && (
        <p role="alert" className="text-sm text-red-700">
          {error}
        </p>
      )}
      {sessions.isPending ? (
        <p role="status" className="text-sm text-muted">
          Loading sessions...
        </p>
      ) : sessions.error ? (
        <p role="alert">Unable to load sessions.</p>
      ) : (
        <ul className="divide-y divide-border border-y border-border">
          {sessions.data?.map((session) => (
            <li
              className="flex items-center justify-between gap-3 py-4"
              key={session.id}
            >
              <div className="min-w-0 text-sm">
                <p className="font-medium">
                  {session.device_label}
                  {session.current ? " (this device)" : ""}
                </p>
                <p className="mt-1 text-xs text-muted">
                  Last active {time(session.last_seen_at)}
                </p>
                <p className="text-xs text-muted">
                  Expires {time(session.expires_at)}
                </p>
              </div>
              <button
                disabled={busy === session.id}
                className="icon-button"
                aria-label="Revoke session"
                title="Revoke session"
                onClick={() => void revoke(session)}
              >
                <LogOut className="h-4 w-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
