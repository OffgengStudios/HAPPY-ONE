"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, useEffect, useMemo, FormEvent } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Archive,
  Check,
  Download,
  FileUp,
  LoaderCircle,
  Pencil,
  Phone,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  X,
} from "lucide-react";
import { all, api, ApiError, Me, time } from "@/lib/api";
import { Field } from "@/lib/demand";
import {
  basicFields,
  contactFields,
  consentFields,
  demographicFields,
  label,
  onboardingState,
  Participant,
  readinessFields,
  reasonField,
  sensitiveFields,
  SupplyItem,
} from "@/lib/supply";
import { DemandForm, Editor } from "./demand-form";
import { Dialog } from "./dialog";
import { CvParserPanel } from "./cv-parser-panel";
import { SupplyCollections } from "./supply-collections";

function Feedback({ pending, error }: { pending: boolean; error: unknown }) {
  return (
    <>
      {pending && (
        <p
          role="status"
          className="flex items-center gap-2 py-6 text-sm text-muted"
        >
          <LoaderCircle className="h-4 w-4 animate-spin" />
          Loading...
        </p>
      )}
      {!!error && (
        <p role="alert" className="py-4 text-sm text-red-700">
          {error instanceof Error ? error.message : "Unable to load."}
        </p>
      )}
    </>
  );
}
function Refresh({ onClick }: { onClick: () => void }) {
  return (
    <button
      className="icon-button"
      title="Refresh"
      aria-label="Refresh"
      onClick={onClick}
    >
      <RefreshCw className="h-4 w-4" />
    </button>
  );
}
function Summary({
  row,
  keys,
}: {
  row: Record<string, unknown>;
  keys: string[];
}) {
  return (
    <dl className="grid gap-x-6 gap-y-5 border-y border-border py-5 sm:grid-cols-2 lg:grid-cols-3">
      {keys.map((key) => (
        <div key={key} className="min-w-0">
          <dt className="mb-1 text-xs text-muted capitalize">
            {key.replaceAll("_", " ").replace(" raw", "").replace(" code", "")}
          </dt>
          <dd className="break-words text-sm">
            {key.endsWith("_at")
              ? time(row[key] as string | null)
              : typeof row[key] === "boolean"
                ? row[key]
                  ? "Yes"
                  : "No"
                : String(row[key] ?? "Not recorded")}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function participantEditor(user: Me, ownerField: Field): Editor {
  return {
    title: "New participant",
    path: "/participants",
    fields: [
      ...basicFields,
      ...contactFields,
      ownerField,
      { key: "source_type", label: "Recruitment source", max: 60 },
      { key: "source_detail", label: "Source detail", max: 200 },
    ],
    initial: {
      assigned_user_id: ownerField.options?.some(
        (owner) => owner.value === user.id,
      )
        ? user.id
        : null,
    },
  };
}
export function SupplyWorkspace({
  view,
  user,
  initialIdentifier = null,
  initialCreate = false,
}: {
  view: string;
  user: Me;
  initialIdentifier?: string | null;
  initialCreate?: boolean;
}) {
  const cache = useQueryClient();
  const [identifier, setIdentifier] = useState<string | null>(
    initialIdentifier,
  );
  const [editor, setEditor] = useState<Editor | null>(null);
  const [createPending, setCreatePending] = useState(initialCreate);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const can = (code: string) => user.permissions.includes(code);
  async function refresh() {
    await cache.invalidateQueries({ queryKey: ["supply"] });
  }
  const owners = useQuery({
    queryKey: ["supply", "owners"],
    queryFn: () => api<{ id: string; full_name: string }[]>("/supply/owners"),
    enabled: can("workspace_supply:view") && can("participant:view"),
  });
  const ownerField: Field = useMemo(
    () => ({
      key: "assigned_user_id",
      label: "Assigned owner",
      type: "select",
      options:
        owners.data?.map((owner) => ({
          value: owner.id,
          label: owner.full_name,
        })) ?? [],
    }),
    [owners.data],
  );
  const waitingForOwners =
    user.permissions.includes("workspace_supply:view") &&
    (owners.isPending || !!owners.error);
  useEffect(() => {
    if (!createPending || waitingForOwners) return;
    setCreatePending(false);
    if (
      user.permissions.includes("participant:create") &&
      user.permissions.includes("participant:view")
    )
      setEditor(participantEditor(user, ownerField));
  }, [createPending, waitingForOwners, user, ownerField]);
  return (
    <>
      {createPending && waitingForOwners && (
        <div className="mb-5 flex items-center justify-between gap-3 border-b border-border pb-4">
          <p
            role={owners.error ? "alert" : "status"}
            className="text-sm text-muted"
          >
            {owners.error ? "Staff options unavailable." : "Loading form..."}
          </p>
          <div className="flex gap-2">
            {owners.error && (
              <button
                className="icon-button"
                type="button"
                aria-label="Retry staff options"
                title="Retry staff options"
                onClick={() => void owners.refetch()}
              >
                <RefreshCw className="h-4 w-4" />
              </button>
            )}
            <button
              type="button"
              className="command"
              onClick={() => setCreatePending(false)}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
      {identifier ? (
        <ParticipantDetail
          key={identifier}
          identifier={identifier}
          user={user}
          ownerField={ownerField}
          onBack={() => setIdentifier(null)}
          onEditor={setEditor}
          onRefresh={refresh}
        />
      ) : view === "dashboard" ? (
        <SupplyDashboard
          onOpen={setIdentifier}
          onFilter={(next) => {
            setFilters(next);
          }}
          filters={filters}
          user={user}
        />
      ) : view === "work" ? (
        <SupplyWork onOpen={setIdentifier} />
      ) : (
        <ParticipantList
          filters={filters}
          onFilters={setFilters}
          onOpen={setIdentifier}
          canCreate={can("participant:create")}
          onCreate={() => setCreatePending(true)}
        />
      )}
      {editor && (
        <DemandForm
          key={editor.path + editor.title}
          editor={editor}
          onClose={() => setEditor(null)}
          onDraftSaved={async () => {
            await refresh();
          }}
          onSaved={async (row) => {
            await refresh();
            setEditor(null);
            if (editor.path === "/participants" && typeof row.id === "string")
              setIdentifier(row.id);
          }}
          onReview={async () => {
            await refresh();
            setEditor(null);
          }}
        />
      )}
    </>
  );
}

function ParticipantList({
  filters,
  onFilters,
  onOpen,
  canCreate,
  onCreate,
}: {
  filters: Record<string, string>;
  onFilters: (filters: Record<string, string>) => void;
  onOpen: (id: string) => void;
  canCreate: boolean;
  onCreate: () => void;
}) {
  const [cursors, setCursors] = useState<(string | null)[]>([null]);
  const cursor = cursors[cursors.length - 1];
  const params = new URLSearchParams({
    ...filters,
    limit: "25",
    ...(cursor ? { cursor } : {}),
  });
  const query = useQuery({
    queryKey: ["supply", "participants", params.toString()],
    queryFn: () =>
      api<{ items: Participant[]; next_cursor: string | null }>(
        "/participants?" + params,
      ),
  });
  function filter(key: string, value: string) {
    setCursors([null]);
    const next = { ...filters };
    if (value) next[key] = value;
    else delete next[key];
    onFilters(next);
  }
  return (
    <>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">Participants</h2>
        <div className="flex gap-2">
          <Refresh onClick={() => void query.refetch()} />
          {canCreate && (
            <button className="command primary" onClick={onCreate}>
              <Plus className="h-4 w-4" />
              New participant
            </button>
          )}
        </div>
      </div>
      <div className="mb-5 flex flex-wrap items-end gap-3">
        <label className="field-label min-w-0 flex-1">
          Search
          <div className="relative">
            <Search className="absolute left-3 top-3 h-4 w-4 text-muted" />
            <input
              className="field pl-9"
              maxLength={200}
              value={filters.q ?? ""}
              onChange={(event) => filter("q", event.target.value)}
            />
          </div>
        </label>
        <label className="field-label">
          Onboarding
          <select
            className="field"
            value={filters.onboarding_status ?? ""}
            onChange={(event) =>
              filter("onboarding_status", event.target.value)
            }
          >
            <option value="">All statuses</option>
            {[
              "NOT_STARTED",
              "IN_PROGRESS",
              "COMPLETE",
              "BLOCKED",
              "WITHDRAWN",
            ].map((value) => (
              <option key={value} value={value}>
                {label(value)}
              </option>
            ))}
          </select>
        </label>
        <label className="field-label">
          Readiness
          <select
            className="field"
            value={filters.readiness_status ?? ""}
            onChange={(event) => filter("readiness_status", event.target.value)}
          >
            <option value="">All readiness</option>
            {["NOT_ASSESSED", "DEVELOPING", "JOB_READY", "NOT_JOB_READY"].map(
              (value) => (
                <option key={value} value={value}>
                  {label(value)}
                </option>
              ),
            )}
          </select>
        </label>
        <label className="flex min-h-10 items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={filters.archived === "true"}
            onChange={(event) =>
              filter("archived", event.target.checked ? "true" : "")
            }
          />
          Archived
        </label>
        {Object.keys(filters).length > 0 && (
          <button
            className="icon-button"
            title="Clear filters"
            aria-label="Clear filters"
            onClick={() => {
              onFilters({});
              setCursors([null]);
            }}
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
      <Feedback pending={query.isPending} error={query.error} />
      {query.data?.items.map((row) => (
        <button
          key={row.id}
          className="data-row w-full text-left"
          onClick={() => onOpen(row.id)}
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="break-words text-sm font-medium">{row.full_name}</p>
              <p className="mt-1 text-xs text-muted">{row.participant_code}</p>
            </div>
            <ArrowRight className="h-4 w-4 shrink-0" />
          </div>
          <p className="mt-2 break-words text-xs text-muted">
            {String(row.community)} | {label(row.onboarding_status)} |{" "}
            {label(row.readiness_status)}
          </p>
        </button>
      ))}
      {query.data?.items.length === 0 && (
        <p className="border-y border-border py-12 text-center text-sm text-muted">
          No participants found
        </p>
      )}
      <div className="mt-5 flex justify-end gap-3">
        <button
          className="icon-button"
          title="Previous page"
          aria-label="Previous page"
          disabled={cursors.length === 1 || query.isPending}
          onClick={() => setCursors(cursors.slice(0, -1))}
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <button
          className="icon-button"
          title="Next page"
          aria-label="Next page"
          disabled={!query.data?.next_cursor || query.isPending}
          onClick={() => setCursors([...cursors, query.data!.next_cursor])}
        >
          <ArrowRight className="h-4 w-4" />
        </button>
      </div>
    </>
  );
}

function SupplyDashboard({
  onOpen,
  onFilter,
  filters,
  user,
}: {
  onOpen: (id: string) => void;
  onFilter: (filters: Record<string, string>) => void;
  filters: Record<string, string>;
  user: Me;
}) {
  const [drilldown, setDrilldown] = useState(false);
  const query = useQuery({
    queryKey: ["supply", "dashboard"],
    queryFn: () =>
      api<{
        metrics: {
          code: string;
          label: string;
          value: number;
          percentage?: number;
          filters: Record<string, string>;
        }[];
      }>("/supply/dashboard"),
  });
  if (drilldown)
    return (
      <>
        <button className="command mb-5" onClick={() => setDrilldown(false)}>
          <ArrowLeft className="h-4 w-4" />
          Dashboard
        </button>
        <ParticipantList
          filters={filters}
          onFilters={onFilter}
          onOpen={onOpen}
          canCreate={false}
          onCreate={() => undefined}
        />
      </>
    );
  return (
    <>
      <div className="mb-6 flex items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">Supply Dashboard</h2>
        <Refresh onClick={() => void query.refetch()} />
      </div>
      <Feedback pending={query.isPending} error={query.error} />
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        {query.data?.metrics.map((metric) => (
          <button
            key={metric.code}
            className="metric-card"
            onClick={() => {
              onFilter(metric.filters);
              setDrilldown(true);
            }}
          >
            <p className="break-words text-sm text-muted">{metric.label}</p>
            <p className="my-3 text-2xl font-semibold">{metric.value}</p>
            {metric.percentage !== undefined && (
              <p className="mb-3 text-xs text-muted">
                {metric.percentage}% of registered
              </p>
            )}
            <ArrowRight className="h-4 w-4 text-muted" />
          </button>
        ))}
      </div>
      <h3 className="mb-4 mt-8 text-base font-semibold">Needs attention</h3>
      <Attention onOpen={onOpen} user={user} />
    </>
  );
}
function Attention({ onOpen }: { onOpen: (id: string) => void; user: Me }) {
  const query = useQuery({
    queryKey: ["supply", "attention"],
    queryFn: () =>
      api<{ items: Participant[] }>("/participants?pending_only=true&limit=10"),
  });
  return (
    <>
      <Feedback pending={query.isPending} error={query.error} />
      {query.data?.items.map((row) => (
        <button
          key={row.id}
          className="data-row w-full text-left"
          onClick={() => onOpen(row.id)}
        >
          <p className="text-sm font-medium">{row.full_name}</p>
          <p className="mt-1 break-words text-xs text-muted">
            {label(row.onboarding_status)} |{" "}
            {row.missing_sections.join(", ") || "Review completion"}
          </p>
        </button>
      ))}
      {query.data?.items.length === 0 && (
        <p className="border-y border-border py-6 text-sm text-muted">
          No pending onboarding
        </p>
      )}
    </>
  );
}
function SupplyWork({ onOpen }: { onOpen: (id: string) => void }) {
  const query = useQuery({
    queryKey: ["supply", "work"],
    queryFn: () => all<Participant>("/supply/my-work"),
  });
  const buckets = [
    {
      name: "Overdue",
      matches: (row: Participant) => row.due_state === "OVERDUE",
    },
    {
      name: "Due today",
      matches: (row: Participant) => row.due_state === "TODAY",
    },
    {
      name: "Upcoming",
      matches: (row: Participant) =>
        ["UPCOMING", "UNSCHEDULED"].includes(String(row.due_state)),
    },
    {
      name: "High priority",
      matches: (row: Participant) =>
        ["HIGH", "URGENT"].includes(String(row.priority)),
    },
    {
      name: "Recently assigned",
      matches: (row: Participant) => Boolean(row.recently_assigned),
    },
  ];
  return (
    <>
      <div className="mb-6 flex items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">My Work</h2>
        <Refresh onClick={() => void query.refetch()} />
      </div>
      <Feedback pending={query.isPending} error={query.error} />
      {buckets.map((bucket) => {
        const rows = query.data?.filter(bucket.matches) ?? [];
        return (
          <section key={bucket.name} aria-label={bucket.name} className="mb-7">
            <h3 className="mb-3 text-sm font-semibold">
              {bucket.name}{" "}
              <span className="ml-2 text-muted">{rows.length}</span>
            </h3>
            {rows.map((row) => (
              <button
                key={row.id}
                className="data-row w-full text-left"
                onClick={() => onOpen(row.id)}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="break-words text-sm">{row.full_name}</p>
                  <span className="text-xs text-muted">
                    {row.next_action_due_at
                      ? time(String(row.next_action_due_at))
                      : "Unscheduled"}
                  </span>
                </div>
                <p className="mt-1 break-words text-xs text-muted">
                  {String(row.next_action ?? "Review onboarding")} |{" "}
                  {label(row.priority)}
                </p>
              </button>
            ))}
            {!query.isPending && rows.length === 0 && (
              <p className="border-y border-border py-5 text-sm text-muted">
                No assigned actions
              </p>
            )}
          </section>
        );
      })}
    </>
  );
}

function ParticipantDetail({
  identifier,
  user,
  ownerField,
  onBack,
  onEditor,
  onRefresh,
}: {
  identifier: string;
  user: Me;
  ownerField: Field;
  onBack: () => void;
  onEditor: (editor: Editor) => void;
  onRefresh: () => Promise<void>;
}) {
  const path = "/participants/" + identifier;
  const [tab, setTab] = useState("Overview");
  const [collection, setCollection] = useState<
    "education" | "employment" | null
  >(null);
  const [uploading, setUploading] = useState(false);
  const [actionError, setActionError] = useState("");
  const [commandBusy, setCommandBusy] = useState(false);
  const query = useQuery({
    queryKey: ["supply", "detail", identifier],
    queryFn: () => api<Participant>(path + "/onboarding"),
  });
  const can = (code: string) => user.permissions.includes(code);
  const sensitiveQuery = useQuery({
    queryKey: ["supply", "sensitive", identifier],
    queryFn: () => api<Record<string, unknown>>(path + "/sensitive"),
    enabled: tab === "Sensitive" && can("participant_sensitive:view"),
  });
  const childQuery = useQuery({
    queryKey: ["supply", "children", identifier, tab],
    queryFn: () =>
      all<SupplyItem>(
        tab === "Consent"
          ? path + "/consents"
          : tab === "Documents"
            ? path + "/cv/versions"
            : path + "/activity",
      ),
    enabled: ["Consent", "Documents", "Activity"].includes(tab),
  });
  const row = query.data;
  const editable = can("participant:edit") && !row?.archived_at;
  const tabs = [
    "Overview",
    "Basic",
    "Contact",
    "Education",
    "Employment",
    "Training",
    "Review",
    "Consent",
    ...(can("cv:view") ? ["Documents"] : []),
    ...(can("participant_sensitive:view") ? ["Sensitive"] : []),
    "Activity",
  ];
  function edit(
    title: string,
    endpoint: string,
    fields: Field[],
    initial?: Record<string, unknown>,
    method = "PATCH",
    extra?: Record<string, unknown>,
  ) {
    if (row)
      onEditor({
        title,
        path: endpoint,
        fields,
        method,
        initial: initial ?? row,
        extra: { version: row.version, ...extra },
        autosave:
          method === "PATCH" &&
          ["basic", "contact", "training", "demographics"].some((section) =>
            endpoint.endsWith("/onboarding/" + section),
          ),
      });
  }
  async function command(endpoint: string) {
    if (!row || commandBusy) return;
    setCommandBusy(true);
    setActionError("");
    try {
      await api(endpoint, "POST", { version: row.version });
      await onRefresh();
    } catch (error) {
      setActionError(
        error instanceof Error ? error.message : "Unable to complete action.",
      );
    } finally {
      setCommandBusy(false);
    }
  }
  async function download(document: SupplyItem) {
    setActionError("");
    try {
      const response = await fetch(
        "/api/v1/files/" + document.id + "/download",
        { credentials: "same-origin", cache: "no-store" },
      );
      if (!response.ok) {
        const error = await response.json();
        if (response.status === 401)
          window.dispatchEvent(new Event("happy:auth-expired"));
        throw new ApiError(
          response.status,
          error.error?.message ?? "Download unavailable.",
        );
      }
      const url = URL.createObjectURL(await response.blob());
      const link = window.document.createElement("a");
      link.href = url;
      link.download =
        "cv-" +
        document.version_number +
        (document.mime_type === "application/pdf" ? ".pdf" : ".docx");
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) {
      setActionError(
        error instanceof Error ? error.message : "Unable to download.",
      );
    }
  }
  return (
    <>
      <button className="command mb-5" onClick={onBack}>
        <ArrowLeft className="h-4 w-4" />
        Back
      </button>
      <Feedback pending={query.isPending} error={query.error} />
      {row && (
        <>
          <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="mb-2 text-xs text-muted">{row.participant_code}</p>
              <h2 className="break-words text-xl font-semibold">
                {row.full_name}
              </h2>
              <p className="mt-2 text-sm capitalize text-muted">
                {row.archived_at ? "Archived" : label(row.onboarding_status)}
              </p>
              {row.completion_mode === "STAFF_ASSISTED" && (
                <p className="mt-2 text-xs text-muted">
                  Staff-assisted onboarding
                </p>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              {typeof row.phone_normalized === "string" && (
                <a className="command" href={"tel:" + row.phone_normalized}>
                  <Phone className="h-4 w-4" />
                  Call
                </a>
              )}
              <Refresh onClick={() => void onRefresh()} />
              {editable && (
                <>
                  <button
                    className="command"
                    disabled={commandBusy}
                    onClick={() =>
                      edit("Assign participant", path, [
                        ownerField,
                        {
                          key: "priority",
                          label: "Priority",
                          type: "select",
                          required: true,
                          options: ["NORMAL", "HIGH", "URGENT"].map(
                            (value) => ({ value, label: label(value) }),
                          ),
                        },
                        { key: "next_action", label: "Next action", max: 500 },
                        {
                          key: "next_action_due_at",
                          label: "Due (Ghana time)",
                          type: "datetime-local",
                        },
                        reasonField,
                      ])
                    }
                  >
                    <Pencil className="h-4 w-4" />
                    Assignment
                  </button>
                  <button
                    className="icon-button"
                    title="Archive participant"
                    aria-label="Archive participant"
                    disabled={commandBusy}
                    onClick={() =>
                      edit(
                        "Archive participant",
                        path + "/archive",
                        [reasonField],
                        {},
                        "POST",
                      )
                    }
                  >
                    <Archive className="h-4 w-4" />
                  </button>
                </>
              )}
            </div>
          </div>
          <div className="mb-5 grid grid-cols-2 gap-4 border-y border-border py-4 sm:grid-cols-4">
            <div>
              <p className="text-xs text-muted">Profile completion</p>
              <p className="mt-2 font-semibold">
                {row.profile_completion_pct}%
              </p>
            </div>
            <div>
              <p className="text-xs text-muted">Readiness</p>
              <p className="mt-2 text-sm capitalize">
                {label(row.readiness_status)}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted">CV</p>
              <p className="mt-2 text-sm capitalize">{label(row.cv_status)}</p>
            </div>
            <div>
              <p className="text-xs text-muted">Employer submission</p>
              <p className="mt-2 text-sm">
                {row.submission_eligible ? "Eligible" : "Blocked"}
              </p>
            </div>
          </div>
          {!row.policy_configured && (
            <p
              role="status"
              className="mb-5 border-l-2 border-amber-500 pl-3 text-sm text-amber-800"
            >
              Onboarding policy pending approval
            </p>
          )}
          <div
            role="tablist"
            aria-label="Participant record"
            className="mb-5 flex flex-wrap border-b border-border"
          >
            {tabs.map((name) => (
              <button
                role="tab"
                id={"supply-tab-" + name}
                aria-controls="supply-panel"
                aria-selected={tab === name}
                key={name}
                className={
                  "border-b-2 px-3 py-3 text-sm " +
                  (tab === name
                    ? "border-primary text-primary"
                    : "border-transparent text-muted")
                }
                onClick={() => {
                  setTab(name);
                  setActionError("");
                }}
              >
                {name}
              </button>
            ))}
          </div>
          {actionError && (
            <p role="alert" className="mb-4 text-sm text-red-700">
              {actionError}
            </p>
          )}
          <div
            role="tabpanel"
            id="supply-panel"
            aria-labelledby={"supply-tab-" + tab}
          >
            {["Overview", "Basic", "Contact", "Training", "Review"].includes(
              tab,
            ) && (
              <>
                {editable && tab !== "Overview" && (
                  <button
                    className="command mb-5"
                    onClick={() =>
                      tab === "Basic"
                        ? edit(
                            "Edit basic details",
                            path + "/onboarding/basic",
                            basicFields,
                          )
                        : tab === "Contact"
                          ? edit("Edit contact", path + "/onboarding/contact", [
                              ...contactFields,
                              basicFields[basicFields.length - 1],
                            ])
                          : tab === "Training"
                            ? edit(
                                "Edit training",
                                path + "/onboarding/training",
                                [
                                  {
                                    key: "training_summary",
                                    label: "Training summary",
                                    type: "textarea",
                                    max: 5000,
                                  },
                                ],
                              )
                            : edit(
                                "Review participant",
                                path + "/onboarding/review",
                                [
                                  {
                                    key: "reviewed",
                                    label: "Profile reviewed by staff",
                                    type: "checkbox",
                                  },
                                ],
                              )
                    }
                  >
                    <Pencil className="h-4 w-4" />
                    {tab === "Review"
                      ? "Record review"
                      : "Edit " + tab.toLowerCase()}
                  </button>
                )}
                {tab !== "Review" && (
                  <Summary
                    row={row}
                    keys={
                      tab === "Basic"
                        ? [
                            "first_name",
                            "surname",
                            "other_names",
                            "implementing_partner",
                          ]
                        : tab === "Contact"
                          ? [
                              "phone_raw",
                              "phone_normalized",
                              "email",
                              "region_code",
                              "district_code",
                              "community",
                              "location_status",
                              "directions",
                            ]
                          : tab === "Training"
                            ? ["training_summary"]
                            : [
                                "source_system",
                                "created_via",
                                "source_type",
                                "source_detail",
                                "community",
                                "availability_status",
                                "completion_mode",
                                "completed_at",
                              ]
                    }
                  />
                )}
                {(tab === "Overview" || tab === "Review") && (
                  <>
                    <h3 className="mb-3 mt-6 text-sm font-semibold">
                      Onboarding checklist
                    </h3>
                    {Array.from(
                      new Set([
                        ...row.required_sections,
                        ...row.completed_sections,
                      ]),
                    ).map((section) => (
                      <div
                        key={section}
                        className="data-row flex items-center justify-between gap-3"
                      >
                        <p className="text-sm capitalize">
                          {section}
                          {row.required_sections.includes(section)
                            ? " (required)"
                            : ""}
                        </p>
                        <span className="text-xs text-muted">
                          {row.completed_sections.includes(section)
                            ? "Complete"
                            : "Pending"}
                        </span>
                      </div>
                    ))}
                    {row.missing_fields.length > 0 && (
                      <p className="mt-4 break-words text-sm text-amber-800">
                        Missing fields:{" "}
                        {row.missing_fields.map(label).join(", ")}
                      </p>
                    )}
                    {editable && (
                      <div className="mt-5 flex flex-wrap gap-3">
                        <button
                          className="command"
                          onClick={() =>
                            edit(
                              "Change onboarding status",
                              path + "/onboarding/transition",
                              [onboardingState, reasonField],
                              { to_status: "IN_PROGRESS" },
                              "POST",
                            )
                          }
                        >
                          <Pencil className="h-4 w-4" />
                          Change status
                        </button>
                        <button
                          className="command primary"
                          disabled={
                            !row.policy_configured ||
                            row.missing_fields.length > 0 ||
                            row.missing_sections.length > 0 ||
                            ["COMPLETE", "WITHDRAWN"].includes(
                              row.onboarding_status,
                            )
                          }
                          onClick={() =>
                            edit(
                              "Complete onboarding",
                              path + "/onboarding/complete",
                              [
                                {
                                  key: "completion_mode",
                                  label: "Completion mode",
                                  type: "select",
                                  required: true,
                                  options: [
                                    {
                                      value: "STAFF_ASSISTED",
                                      label: "Staff assisted",
                                    },
                                    {
                                      value: "SELF_REPORTED",
                                      label: "Self reported",
                                    },
                                  ],
                                },
                              ],
                              { completion_mode: "STAFF_ASSISTED" },
                              "POST",
                            )
                          }
                        >
                          <Check className="h-4 w-4" />
                          Complete onboarding
                        </button>
                        <button
                          className="command"
                          onClick={() =>
                            edit(
                              "Assess readiness",
                              path + "/readiness",
                              readinessFields,
                              undefined,
                              "POST",
                            )
                          }
                        >
                          <ShieldCheck className="h-4 w-4" />
                          Assess readiness
                        </button>
                      </div>
                    )}
                  </>
                )}
              </>
            )}
            {(tab === "Education" || tab === "Employment") && (
              <>
                {editable && (
                  <button
                    className="command mb-5"
                    onClick={() =>
                      setCollection(
                        tab === "Education" ? "education" : "employment",
                      )
                    }
                  >
                    <Pencil className="h-4 w-4" />
                    Edit {tab.toLowerCase()}
                  </button>
                )}
                {tab === "Employment" && (
                  <Summary
                    row={row}
                    keys={[
                      "employment_status",
                      "current_occupation",
                      "sector_code",
                      "industry_code",
                      "job_type",
                      "job_role",
                      "work_region_code",
                      "work_district_code",
                      "work_community",
                    ]}
                  />
                )}
                {(tab === "Education"
                  ? ["education"]
                  : ["experience", "skills"]
                ).map((group) => (
                  <section key={group} className="mt-5">
                    <h3 className="mb-3 text-sm font-semibold capitalize">
                      {group}
                    </h3>
                    {((row[group] as SupplyItem[]) ?? []).map((item) => (
                      <div key={item.id} className="data-row">
                        <p className="break-words text-sm font-medium">
                          {String(
                            item.education_level ??
                              item.role_title ??
                              item.skill_name,
                          )}
                        </p>
                        <p className="mt-1 break-words text-xs text-muted">
                          {String(
                            item.institution ??
                              item.employer_name ??
                              item.level ??
                              "",
                          )}
                        </p>
                      </div>
                    ))}
                    {((row[group] as SupplyItem[]) ?? []).length === 0 && (
                      <p className="py-5 text-sm text-muted">None recorded</p>
                    )}
                  </section>
                ))}
              </>
            )}
            {tab === "Sensitive" && (
              <>
                <Feedback
                  pending={sensitiveQuery.isPending}
                  error={sensitiveQuery.error}
                />
                {sensitiveQuery.data && (
                  <>
                    {editable && can("participant_sensitive:edit") && (
                      <div className="mb-5 flex flex-wrap gap-3">
                        <button
                          className="command"
                          onClick={() =>
                            edit(
                              "Edit demographics",
                              path + "/onboarding/demographics",
                              demographicFields,
                              sensitiveQuery.data,
                            )
                          }
                        >
                          <Pencil className="h-4 w-4" />
                          Demographics
                        </button>
                        <button
                          className="command"
                          onClick={() =>
                            edit(
                              "Edit sensitive details",
                              path + "/sensitive",
                              sensitiveFields,
                              sensitiveQuery.data,
                            )
                          }
                        >
                          <Pencil className="h-4 w-4" />
                          Sensitive details
                        </button>
                        <button
                          className="command"
                          onClick={() =>
                            edit(
                              "Record identity",
                              path + "/identity",
                              [
                                {
                                  key: "government_id_type",
                                  label: "Identity type",
                                  type: "select",
                                  required: true,
                                  options: [
                                    {
                                      value: "GHANA_CARD",
                                      label: "Ghana card",
                                    },
                                    { value: "VOTER_ID", label: "Voter ID" },
                                  ],
                                },
                                {
                                  key: "government_id",
                                  label: "Identity reference",
                                  type: "password",
                                  required: true,
                                  max: 80,
                                },
                              ],
                              {},
                            )
                          }
                        >
                          <ShieldCheck className="h-4 w-4" />
                          Identity
                        </button>
                      </div>
                    )}
                    <Summary
                      row={sensitiveQuery.data}
                      keys={[
                        "date_of_birth",
                        "age",
                        "sex",
                        "nationality",
                        "government_id_type",
                        "has_government_id",
                        ...sensitiveFields.map((field) => field.key),
                      ]}
                    />
                  </>
                )}
              </>
            )}
            {["Consent", "Documents", "Activity"].includes(tab) && (
              <>
                <div className="mb-5 flex flex-wrap gap-3">
                  <Refresh onClick={() => void childQuery.refetch()} />
                  {tab === "Consent" && editable && (
                    <button
                      className="command"
                      onClick={() =>
                        edit(
                          "Record consent",
                          path + "/consents",
                          consentFields,
                          {
                            consent_type: "PROGRAMME",
                            method: "STAFF_RECORDED",
                            privacy_notice_version:
                              row.privacy_notice_version ?? "",
                          },
                          "POST",
                        )
                      }
                    >
                      <Plus className="h-4 w-4" />
                      Record consent
                    </button>
                  )}
                  {tab === "Documents" &&
                    !row.archived_at &&
                    can("cv:edit") && (
                      <>
                        <button
                          className="command"
                          disabled={commandBusy}
                          onClick={() => setUploading(true)}
                        >
                          <FileUp className="h-4 w-4" />
                          Upload CV
                        </button>
                        <button
                          className="command"
                          disabled={commandBusy}
                          onClick={() =>
                            edit(
                              "CV not required",
                              path + "/cv/not-required",
                              [reasonField],
                              {},
                              "POST",
                            )
                          }
                        >
                          <X className="h-4 w-4" />
                          CV not required
                        </button>
                      </>
                    )}
                </div>
                <Feedback
                  pending={childQuery.isPending}
                  error={childQuery.error}
                />
                {childQuery.data?.map((item) => (
                  <div key={item.id} className="data-row">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="break-words text-sm font-medium">
                          {tab === "Consent"
                            ? label(item.consent_type) + " consent"
                            : tab === "Documents"
                              ? String(item.original_filename)
                              : label(item.event_code).replace(".", ": ")}
                        </p>
                        <p className="mt-1 break-words text-xs text-muted">
                          {tab === "Consent"
                            ? label(item.status) +
                              " | " +
                              String(item.privacy_notice_version) +
                              " | " +
                              time(item.consented_at as string)
                            : tab === "Documents"
                              ? "Version " +
                                item.version_number +
                                " | " +
                                label(item.scan_status) +
                                (item.id === row.current_cv_id
                                  ? " | Current approved CV"
                                  : "")
                              : time(item.occurred_at as string) +
                                " | " +
                                String(item.actor_type)}
                        </p>
                        {tab === "Consent" && !!item.withdrawn_at && (
                          <p className="mt-2 text-xs text-muted">
                            Withdrawn {time(item.withdrawn_at as string)}
                          </p>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {tab === "Consent" &&
                          editable &&
                          item.status === "ACTIVE" && (
                            <button
                              className="command"
                              onClick={() =>
                                edit(
                                  "Withdraw consent",
                                  "/consents/" + item.id + "/withdraw",
                                  [reasonField],
                                  {},
                                  "POST",
                                )
                              }
                            >
                              <X className="h-4 w-4" />
                              Withdraw
                            </button>
                          )}
                        {tab === "Documents" &&
                          !row.archived_at &&
                          !item.archived_at && (
                            <>
                              {item.scan_status === "AVAILABLE" &&
                                can("cv:download") && (
                                  <button
                                    className="icon-button"
                                    title="Download CV"
                                    aria-label={
                                      "Download CV version " +
                                      item.version_number
                                    }
                                    onClick={() => void download(item)}
                                  >
                                    <Download className="h-4 w-4" />
                                  </button>
                                )}
                              {can("cv:edit") && (
                                <>
                                  {item.scan_status === "AVAILABLE" &&
                                    item.id !== row.current_cv_id && (
                                      <button
                                        className="command"
                                        disabled={commandBusy}
                                        onClick={() =>
                                          void command(
                                            "/cv/" + item.id + "/approve",
                                          )
                                        }
                                      >
                                        <Check className="h-4 w-4" />
                                        Approve CV
                                      </button>
                                    )}
                                  {item.scan_status === "SCANNING" && (
                                    <button
                                      className="command"
                                      disabled={commandBusy}
                                      onClick={() =>
                                        void command(
                                          "/files/" + item.id + "/rescan",
                                        )
                                      }
                                    >
                                      <RefreshCw className="h-4 w-4" />
                                      Rescan
                                    </button>
                                  )}
                                  <button
                                    className="icon-button"
                                    title="Archive CV"
                                    aria-label={
                                      "Archive CV version " +
                                      item.version_number
                                    }
                                    disabled={commandBusy}
                                    onClick={() =>
                                      edit(
                                        "Archive CV",
                                        "/files/" + item.id + "/archive",
                                        [reasonField],
                                        {},
                                        "POST",
                                      )
                                    }
                                  >
                                    <Archive className="h-4 w-4" />
                                  </button>
                                </>
                              )}
                            </>
                          )}
                      </div>
                    </div>
                    {tab === "Documents" &&
                      item.scan_status === "AVAILABLE" &&
                      !item.archived_at && (
                        <CvParserPanel
                          document={item}
                          participant={row}
                          user={user}
                          refresh={onRefresh}
                        />
                      )}
                  </div>
                ))}
                {childQuery.data?.length === 0 && (
                  <p className="border-y border-border py-8 text-sm text-muted">
                    None recorded
                  </p>
                )}
              </>
            )}
          </div>
          {collection && (
            <SupplyCollections
              section={collection}
              participant={row}
              onClose={() => setCollection(null)}
              onSaved={onRefresh}
            />
          )}
          {uploading && (
            <UploadCV
              row={row}
              onClose={() => setUploading(false)}
              onSaved={onRefresh}
            />
          )}
        </>
      )}
    </>
  );
}
function UploadCV({
  row,
  onClose,
  onSaved,
}: {
  row: Participant;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const body = new FormData(event.currentTarget);
    body.set("version", String(row.version));
    try {
      await api("/participants/" + row.id + "/cv", "POST", body);
      await onSaved();
      onClose();
    } catch (error) {
      setError(error instanceof Error ? error.message : "Upload failed.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      title="Upload CV"
      placement="action"
      onClose={() => {
        if (!busy) onClose();
      }}
    >
      <form className="space-y-5 p-5" onSubmit={submit}>
        <label className="field-label">
          CV document
          <input
            className="field"
            name="file"
            type="file"
            accept="application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            required
            disabled={busy}
          />
        </label>
        {error && (
          <p role="alert" className="text-sm text-red-700">
            {error}
          </p>
        )}
        <div className="action-footer">
          <button
            className="command"
            type="button"
            disabled={busy}
            onClick={onClose}
          >
            Cancel
          </button>
          <button className="command primary" disabled={busy}>
            <FileUp className="h-4 w-4" />
            Upload
          </button>
        </div>
      </form>
    </Dialog>
  );
}
