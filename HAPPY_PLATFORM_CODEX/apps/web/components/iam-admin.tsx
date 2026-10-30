"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Check,
  FileClock,
  LoaderCircle,
  Pencil,
  Plus,
  RefreshCw,
  Save,
  Search,
  X,
} from "lucide-react";
import { FormEvent, useState } from "react";
import {
  all,
  api,
  Audit,
  Me,
  Override,
  Permission,
  Role,
  time,
  User,
} from "@/lib/api";
import { Dialog } from "./dialog";
import { PasswordInput } from "./password-input";

export function IamAdmin({ view, user }: { view: string; user: Me }) {
  const [editor, setEditor] = useState<User | Role | null | undefined>(
    undefined,
  );
  const [search, setSearch] = useState("");
  const path = view === "audit" ? "/audit-events" : "/" + view;
  const query = useQuery({
    queryKey: [view],
    queryFn: () => all<User | Role | Audit>(path),
  });
  const client = useQueryClient();
  const canRoles = user.permissions.includes("role:manage");
  const roles = useQuery({
    queryKey: ["roles"],
    queryFn: () => all<Role>("/roles"),
    enabled: view === "users" && canRoles,
  });
  const permissions = useQuery({
    queryKey: ["permissions"],
    queryFn: () => all<Permission>("/permissions"),
    enabled: canRoles && view !== "audit",
  });
  const title =
    view === "users"
      ? "Accounts"
      : view === "roles"
        ? "Roles"
        : "Audit history";
  const referencesUnavailable =
    canRoles &&
    view !== "audit" &&
    (permissions.isPending ||
      !!permissions.error ||
      (view === "users" && (roles.isPending || !!roles.error)));
  const rows = query.data?.filter((row) =>
    JSON.stringify(row).toLowerCase().includes(search.toLowerCase()),
  );
  async function saved() {
    setEditor(undefined);
    await client.invalidateQueries({ queryKey: [view] });
    await client.invalidateQueries({ queryKey: ["me"] });
  }
  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">{title}</h2>
        <div className="flex gap-2">
          <button
            className="icon-button"
            title={"Refresh " + title.toLowerCase()}
            aria-label={"Refresh " + title.toLowerCase()}
            onClick={() => {
              void query.refetch();
              if (canRoles && view !== "audit") void permissions.refetch();
              if (canRoles && view === "users") void roles.refetch();
            }}
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          {view !== "audit" && (
            <button
              className="command primary"
              disabled={referencesUnavailable}
              onClick={() => setEditor(null)}
            >
              <Plus className="h-4 w-4" />
              {view === "users" ? "New account" : "New role"}
            </button>
          )}
        </div>
      </div>
      <label className="relative mb-5 block max-w-md">
        <Search
          className="absolute left-3 top-3 h-4 w-4 text-muted"
          aria-hidden="true"
        />
        <input
          className="field pl-9"
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder={"Search " + title.toLowerCase()}
          aria-label={"Search " + title.toLowerCase()}
        />
      </label>
      {query.isPending && (
        <p className="text-sm text-muted" role="status">
          Loading...
        </p>
      )}
      {query.error && (
        <p role="alert" className="text-sm text-red-700">
          {query.error.message}
        </p>
      )}
      {canRoles &&
        view !== "audit" &&
        (permissions.error || (view === "users" && roles.error)) && (
          <p role="alert" className="mb-4 text-sm text-red-700">
            Unable to load role or permission choices.
          </p>
        )}
      {view === "users" && (
        <div>
          <div className="hidden grid-cols-[minmax(0,2fr)_minmax(0,1fr)_80px_36px] gap-3 border-b border-border pb-3 text-xs text-muted md:grid">
            <span>Account</span>
            <span>Roles</span>
            <span>Status</span>
          </div>
          {rows?.map((item) => {
            const row = item as User;
            return (
              <div
                key={row.id}
                className="data-row grid-cols-[minmax(0,1fr)_36px] md:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_80px_36px]"
              >
                <div className="min-w-0">
                  <p className="font-medium">{row.full_name}</p>
                  <p className="mt-1 break-all text-xs text-muted">
                    {row.email}
                  </p>
                </div>
                <p className="col-start-1 row-start-2 text-xs md:col-auto md:row-auto">
                  {row.roles.map((role) => role.name).join(", ") || "No roles"}
                </p>
                <p className="col-start-1 row-start-3 text-xs md:col-auto md:row-auto">
                  {row.is_active ? "Active" : "Inactive"}
                </p>
                <button
                  className="icon-button col-start-2 row-start-1 md:col-auto md:row-auto"
                  title={"Edit " + row.full_name}
                  aria-label={"Edit " + row.full_name}
                  onClick={() => setEditor(row)}
                  disabled={referencesUnavailable}
                >
                  <Pencil className="h-4 w-4" />
                </button>
              </div>
            );
          })}
        </div>
      )}
      {view === "roles" && (
        <div>
          {rows?.map((item) => {
            const row = item as Role;
            return (
              <div
                key={row.id}
                className="data-row grid-cols-[minmax(0,1fr)_36px]"
              >
                <div>
                  <p className="font-medium">{row.name}</p>
                  <p className="mt-1 text-xs text-muted">
                    {row.code} | {row.permission_codes.length} permissions
                    {row.is_system_role ? " | System role" : ""}
                  </p>
                  <p className="mt-2 text-xs text-muted">{row.description}</p>
                </div>
                <button
                  className="icon-button"
                  title={"Edit " + row.name}
                  aria-label={"Edit " + row.name}
                  onClick={() => setEditor(row)}
                  disabled={referencesUnavailable}
                >
                  <Pencil className="h-4 w-4" />
                </button>
              </div>
            );
          })}
        </div>
      )}
      {view === "audit" && (
        <div>
          {rows?.map((item) => {
            const row = item as Audit;
            return (
              <details
                key={row.id}
                className="border-b border-border py-4 text-sm"
              >
                <summary className="cursor-pointer">
                  <span className="font-medium">{row.event_code}</span>
                  <span className="ml-3 text-xs text-muted">{row.result}</span>
                  <span className="mt-1 block text-xs text-muted">
                    {time(row.occurred_at)}
                  </span>
                </summary>
                <dl className="mt-4 grid min-w-0 gap-3 text-xs sm:grid-cols-2">
                  <div>
                    <dt className="text-muted">Actor</dt>
                    <dd className="mt-1 break-all">
                      {row.actor_type}: {row.actor_id ?? "System"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted">Entity</dt>
                    <dd className="mt-1 break-all">
                      {row.entity_type}: {row.entity_id ?? "None"}
                    </dd>
                  </div>
                </dl>
                <pre className="mt-3 overflow-auto rounded-md bg-gray-50 p-3 text-xs">
                  {JSON.stringify(
                    { metadata: row.metadata, changes: row.after },
                    null,
                    2,
                  )}
                </pre>
              </details>
            );
          })}
        </div>
      )}
      {!query.isPending && !query.error && rows?.length === 0 && (
        <div className="flex flex-col items-center gap-3 border-y border-border py-16 text-sm text-muted">
          <FileClock className="h-6 w-6" />
          <p>No matching records</p>
        </div>
      )}
      {editor !== undefined && view === "users" && (
        <UserEditor
          key={editor?.id ?? "new"}
          value={editor as User | null}
          roles={roles.data ?? []}
          permissions={permissions.data ?? []}
          canRoles={canRoles}
          loading={canRoles && (roles.isPending || permissions.isPending)}
          onClose={() => setEditor(undefined)}
          onSaved={saved}
        />
      )}
      {editor !== undefined && view === "roles" && (
        <RoleEditor
          key={editor?.id ?? "new"}
          value={editor as Role | null}
          permissions={permissions.data ?? []}
          loading={permissions.isPending}
          onClose={() => setEditor(undefined)}
          onSaved={saved}
        />
      )}
    </div>
  );
}

function UserEditor({
  value,
  roles,
  permissions,
  canRoles,
  loading,
  onClose,
  onSaved,
}: {
  value: User | null;
  roles: Role[];
  permissions: Permission[];
  canRoles: boolean;
  loading: boolean;
  onClose: () => void;
  onSaved: () => Promise<unknown>;
}) {
  const [name, setName] = useState(value?.full_name ?? "");
  const [email, setEmail] = useState(value?.email ?? "");
  const [password, setPassword] = useState("");
  const [active, setActive] = useState(value?.is_active ?? true);
  const [assigned, setAssigned] = useState(
    value?.roles.map((role) => role.id) ?? [],
  );
  const [primary, setPrimary] = useState(value?.primary_role_id ?? "");
  const [overrides, setOverrides] = useState<Override[]>(
    value?.overrides ?? [],
  );
  const [overrideCode, setOverrideCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const roleData = canRoles
      ? {
          role_ids: assigned,
          primary_role_id: assigned.includes(primary) ? primary : null,
        }
      : {};
    try {
      if (value)
        await api("/users/" + value.id, "PATCH", {
          version: value.version,
          full_name: name,
          is_active: active,
          ...roleData,
          ...(canRoles ? { overrides } : {}),
          ...(password ? { password } : {}),
        });
      else
        await api("/users", "POST", {
          email,
          full_name: name,
          password,
          ...roleData,
        });
      await onSaved();
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Unable to save account.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      title={value ? "Edit account" : "New account"}
      placement="action"
      onClose={onClose}
    >
      <form className="space-y-5 p-5" onSubmit={submit}>
        <label className="field-label">
          Full name
          <input
            className="field"
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
            maxLength={150}
            autoFocus
          />
        </label>
        <label className="field-label">
          Email
          <input
            className="field"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            disabled={!!value}
            required
            maxLength={254}
            autoComplete="off"
          />
        </label>
        <div className="field-label">
          <label htmlFor="account-password">
            {value ? "New password" : "Password"}
          </label>
          <PasswordInput
            id="account-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required={!value}
            minLength={12}
            maxLength={128}
            autoComplete="new-password"
            visibilityDisabled={busy}
          />
        </div>
        {value && (
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={active}
              onChange={(event) => setActive(event.target.checked)}
            />
            Active account
          </label>
        )}
        {canRoles && (
          <>
            <fieldset>
              <legend className="mb-3 text-sm font-medium">
                Assigned roles
              </legend>
              <div className="grid gap-3 sm:grid-cols-2">
                {roles.map((role) => (
                  <label
                    className="flex items-center gap-2 text-sm"
                    key={role.id}
                  >
                    <input
                      type="checkbox"
                      checked={assigned.includes(role.id)}
                      onChange={(event) =>
                        setAssigned(
                          event.target.checked
                            ? [...assigned, role.id]
                            : assigned.filter((id) => id !== role.id),
                        )
                      }
                    />
                    {role.name}
                  </label>
                ))}
              </div>
            </fieldset>
            <label className="field-label">
              Primary role
              <select
                className="field"
                value={assigned.includes(primary) ? primary : ""}
                onChange={(event) => setPrimary(event.target.value)}
              >
                <option value="">No default</option>
                {roles
                  .filter((role) => assigned.includes(role.id))
                  .map((role) => (
                    <option key={role.id} value={role.id}>
                      {role.name}
                    </option>
                  ))}
              </select>
            </label>
            {value && (
              <fieldset>
                <legend className="mb-3 text-sm font-medium">
                  Permission overrides
                </legend>
                <div className="mb-3 flex gap-2">
                  <select
                    className="field"
                    aria-label="Override permission"
                    value={overrideCode}
                    onChange={(event) => setOverrideCode(event.target.value)}
                  >
                    <option value="">Select permission</option>
                    {permissions
                      .filter(
                        (permission) =>
                          !overrides.some(
                            (item) => item.code === permission.code,
                          ),
                      )
                      .map((permission) => (
                        <option key={permission.id} value={permission.code}>
                          {permission.code}
                        </option>
                      ))}
                  </select>
                  <button
                    type="button"
                    className="icon-button"
                    title="Add override"
                    aria-label="Add override"
                    disabled={!overrideCode}
                    onClick={() => {
                      setOverrides([
                        ...overrides,
                        { code: overrideCode, effect: "DENY" },
                      ]);
                      setOverrideCode("");
                    }}
                  >
                    <Plus className="h-4 w-4" />
                  </button>
                </div>
                {overrides.map((override) => (
                  <div
                    className="mb-3 flex flex-wrap items-center gap-2"
                    key={override.code}
                  >
                    <span className="min-w-0 flex-1 break-all text-xs">
                      {override.code}
                    </span>
                    <select
                      className="field w-24"
                      aria-label={"Effect for " + override.code}
                      value={override.effect}
                      onChange={(event) =>
                        setOverrides(
                          overrides.map((item) =>
                            item.code === override.code
                              ? {
                                  ...item,
                                  effect: event.target
                                    .value as Override["effect"],
                                }
                              : item,
                          ),
                        )
                      }
                    >
                      <option value="DENY">Deny</option>
                      <option value="ALLOW">Allow</option>
                    </select>
                    <button
                      className="icon-button"
                      type="button"
                      aria-label={"Remove " + override.code}
                      title="Remove override"
                      onClick={() =>
                        setOverrides(
                          overrides.filter(
                            (item) => item.code !== override.code,
                          ),
                        )
                      }
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </fieldset>
            )}
          </>
        )}
        {error && (
          <p className="text-sm text-red-700" role="alert">
            {error}
          </p>
        )}
        <div className="action-footer">
          <button type="button" className="command" onClick={onClose}>
            Cancel
          </button>
          <button className="command primary" disabled={busy || loading}>
            {busy ? (
              <LoaderCircle className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            Save account
          </button>
        </div>
      </form>
    </Dialog>
  );
}

function RoleEditor({
  value,
  permissions,
  loading,
  onClose,
  onSaved,
}: {
  value: Role | null;
  permissions: Permission[];
  loading: boolean;
  onClose: () => void;
  onSaved: () => Promise<unknown>;
}) {
  const [code, setCode] = useState(value?.code ?? "");
  const [name, setName] = useState(value?.name ?? "");
  const [description, setDescription] = useState(value?.description ?? "");
  const [codes, setCodes] = useState(value?.permission_codes ?? []);
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api(
        value ? "/roles/" + value.id : "/roles",
        value ? "PATCH" : "POST",
        {
          ...(value ? { version: value.version } : { code }),
          name,
          description,
          ...(value?.code === "ADMIN" ? {} : { permission_codes: codes }),
        },
      );
      await onSaved();
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unable to save role.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      title={value ? "Edit role" : "New role"}
      placement="action"
      onClose={onClose}
    >
      <form className="space-y-5 p-5" onSubmit={submit}>
        <label className="field-label">
          Role code
          <input
            className="field"
            value={code}
            onChange={(event) => setCode(event.target.value.toUpperCase())}
            disabled={!!value}
            required
            pattern="[A-Z][A-Z0-9_]{2,39}"
            maxLength={40}
          />
        </label>
        <label className="field-label">
          Role name
          <input
            className="field"
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
            maxLength={100}
          />
        </label>
        <label className="field-label">
          Description
          <textarea
            className="field"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            maxLength={1000}
            rows={2}
          />
        </label>
        <fieldset>
          <legend className="mb-3 text-sm font-medium">Permissions</legend>
          <input
            className="field mb-3"
            type="search"
            placeholder="Filter permissions"
            aria-label="Filter permissions"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <div className="max-h-56 space-y-3 overflow-y-auto border-y border-border py-3">
            {permissions
              .filter((permission) => permission.code.includes(search))
              .sort((a, b) => a.code.localeCompare(b.code))
              .map((permission) => (
                <label
                  key={permission.id}
                  className="flex items-start gap-2 text-xs"
                >
                  <input
                    className="mt-0.5"
                    type="checkbox"
                    checked={codes.includes(permission.code)}
                    disabled={value?.code === "ADMIN"}
                    onChange={(event) =>
                      setCodes(
                        event.target.checked
                          ? [...codes, permission.code]
                          : codes.filter((item) => item !== permission.code),
                      )
                    }
                  />
                  <span className="break-all">{permission.code}</span>
                </label>
              ))}
          </div>
          <p className="mt-2 flex items-center gap-1 text-xs text-muted">
            <Check className="h-3 w-3" />
            {codes.length} selected
          </p>
        </fieldset>
        {error && (
          <p role="alert" className="text-sm text-red-700">
            {error}
          </p>
        )}
        <div className="action-footer">
          <button type="button" className="command" onClick={onClose}>
            Cancel
          </button>
          <button className="command primary" disabled={busy || loading}>
            {busy ? (
              <LoaderCircle className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            Save role
          </button>
        </div>
      </form>
    </Dialog>
  );
}
