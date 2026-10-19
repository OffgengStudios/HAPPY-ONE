export type Role = {
  id: string;
  code: string;
  name: string;
  description: string;
  is_system_role: boolean;
  version: number;
  permission_codes: string[];
};
export type Override = { code: string; effect: "ALLOW" | "DENY" };
export type User = {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  mfa_enabled: boolean;
  primary_role_id: string | null;
  roles: Role[];
  overrides: Override[];
  version: number;
  last_login_at: string | null;
};
export type Me = User & {
  permissions: string[];
  workspaces: { code: string; name: string }[];
};
export type Permission = {
  id: string;
  code: string;
  resource: string;
  action: string;
};
export type Session = {
  id: string;
  device_label: string;
  created_at: string;
  last_seen_at: string;
  expires_at: string;
  current: boolean;
};
export type Audit = {
  id: string;
  event_code: string;
  actor_id: string | null;
  actor_type: "USER" | "PARTICIPANT" | "EMPLOYER" | "SYSTEM" | "INTEGRATION";
  entity_type: string;
  entity_id: string | null;
  result: string;
  occurred_at: string;
  metadata: Record<string, unknown>;
  after: Record<string, unknown> | null;
};

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public code = "",
  ) {
    super(message);
  }
}

export async function api<T>(
  path: string,
  method = "GET",
  data?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const csrf =
    typeof document === "undefined"
      ? ""
      : (document.cookie
          .split("; ")
          .find((cookie) => cookie.startsWith("happy_csrf="))
          ?.slice("happy_csrf=".length) ?? "");
  const response = await fetch("/api/v1" + path, {
    method,
    credentials: "same-origin",
    cache: "no-store",
    ...(signal ? { signal } : {}),
    headers: {
      ...(data instanceof FormData
        ? {}
        : { "Content-Type": "application/json" }),
      ...(csrf ? { "X-CSRF-Token": decodeURIComponent(csrf) } : {}),
    },
    ...(data === undefined
      ? {}
      : { body: data instanceof FormData ? data : JSON.stringify(data) }),
  });
  if (!response.ok) {
    const result = await response.json().catch(() => null);
    if (
      response.status === 401 &&
      !["/auth/me", "/auth/login", "/auth/mfa/verify"].includes(path)
    ) {
      window.dispatchEvent(new Event("happy:auth-expired"));
    }
    throw new ApiError(
      response.status,
      result?.error?.message ?? "Unable to complete the request.",
      result?.error?.code ?? "",
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export async function all<T>(path: string): Promise<T[]> {
  const items: T[] = [];
  let cursor: string | null = null;
  do {
    const url = new URL(path, "http://happy.invalid");
    url.searchParams.set("limit", "100");
    if (cursor) url.searchParams.set("cursor", cursor);
    else url.searchParams.delete("cursor");
    const page: { items: T[]; next_cursor: string | null } = await api(
      url.pathname + url.search,
    );
    items.push(...page.items);
    cursor = page.next_cursor;
  } while (cursor);
  return items;
}

export async function download(path: string, data: unknown): Promise<void> {
  const csrf =
    document.cookie
      .split("; ")
      .find((cookie) => cookie.startsWith("happy_csrf="))
      ?.slice("happy_csrf=".length) ?? "";
  const response = await fetch("/api/v1" + path, {
    method: "POST",
    credentials: "same-origin",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(csrf ? { "X-CSRF-Token": decodeURIComponent(csrf) } : {}),
    },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const result = await response.json().catch(() => null);
    throw new ApiError(
      response.status,
      result?.error?.message ?? "Unable to download the report.",
      result?.error?.code ?? "",
    );
  }
  const blob = await response.blob();
  const disposition = response.headers.get("content-disposition") ?? "";
  const filename = disposition.match(/filename="([^"]+)"/)?.[1] ?? "report.csv";
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export async function downloadGet(path: string): Promise<void> {
  const response = await fetch("/api/v1" + path, {
    credentials: "same-origin",
    cache: "no-store",
  });
  if (!response.ok) {
    const result = await response.json().catch(() => null);
    throw new ApiError(
      response.status,
      result?.error?.message ?? "Unable to download the report.",
      result?.error?.code ?? "",
    );
  }
  const blob = await response.blob();
  const disposition = response.headers.get("content-disposition") ?? "";
  const filename = disposition.match(/filename="([^"]+)"/)?.[1] ?? "report.csv";
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function time(value: string | null) {
  return value
    ? new Intl.DateTimeFormat("en-GH", {
        timeZone: "Africa/Accra",
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "numeric",
        minute: "2-digit",
      }).format(new Date(value))
    : "Never";
}
