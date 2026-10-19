"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  Archive,
  Building2,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  Download,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Upload,
} from "lucide-react";
import { useEffect, useState } from "react";
import { all, api, ApiError, downloadGet, Me, time } from "@/lib/api";
import {
  contactFields,
  DemandPage,
  DemandRecord,
  display,
  employerFields,
  Field,
  Owner,
  partnershipFields,
  reasonField,
  requirementFields,
  vacancyFields,
} from "@/lib/demand";
import { DemandForm, Editor } from "./demand-form";

type Kind = "employers" | "vacancies";
function employerEditor(fields: Field[], user: Me): Editor {
  return {
    title: "New employer",
    path: "/organizations",
    fields: [
      ...fields,
      { key: "mou_required", label: "MOU required", type: "checkbox" },
    ],
    initial: {
      organization_type: "EMPLOYER",
      mou_required: true,
      relationship_owner_id: user.permissions.includes("workspace_demand:view")
        ? user.id
        : null,
    },
  };
}
function vacancyEditor(
  fields: Field[],
  employers: DemandRecord[],
  user: Me,
  organizationId?: string,
): Editor {
  return {
    title: "New vacancy",
    path: "/vacancies",
    fields: organizationId
      ? fields
      : [
          {
            key: "organization_id",
            label: "Employer",
            type: "select",
            required: true,
            options: employers.map((row) => ({
              value: row.id,
              label: String(row.name),
            })),
          },
          ...fields,
        ],
    initial: {
      required_headcount: 1,
      priority: "NORMAL",
      salary_currency: "GHS",
      demand_owner_id: user.permissions.includes("workspace_demand:view")
        ? user.id
        : null,
    },
    extra: organizationId ? { organization_id: organizationId } : {},
  };
}
const pathFor = (kind: Kind) =>
  kind === "employers" ? "/organizations" : "/vacancies";
const label = (value: unknown) =>
  display(value).replaceAll("_", " ").toLowerCase();
type Metric = {
  code: string;
  label: string;
  value: number;
  resource: Kind;
  filters: Record<string, string>;
};

function Feedback({
  pending,
  error,
}: {
  pending: boolean;
  error: Error | null;
}) {
  if (pending)
    return (
      <p role="status" className="py-6 text-sm text-muted">
        Loading records...
      </p>
    );
  if (error)
    return (
      <p role="alert" className="py-4 text-sm text-red-700">
        {error.message}
      </p>
    );
  return null;
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
function Details({ fields, row }: { fields: Field[]; row: DemandRecord }) {
  return (
    <dl className="grid gap-x-8 gap-y-5 border-y border-border py-5 sm:grid-cols-2 xl:grid-cols-3">
      {fields
        .filter(
          (field) => !["duplicate_acknowledged", "reason"].includes(field.key),
        )
        .map((field) => {
          const value = row[field.key];
          const option = field.options?.find(
            (option) => option.value === String(value),
          );
          return (
            <div className="min-w-0" key={field.key}>
              <dt className="text-xs text-muted">{field.label}</dt>
              <dd className="mt-1 whitespace-pre-wrap break-words text-sm">
                {option?.label ?? display(value)}
              </dd>
            </div>
          );
        })}
    </dl>
  );
}

export function DemandWorkspace({
  view,
  user,
  initialSelection = null,
  initialCreate = false,
}: {
  view: string;
  user: Me;
  initialSelection?: { kind: Kind; id: string } | null;
  initialCreate?: boolean;
}) {
  const client = useQueryClient();
  const [screen, setScreen] = useState(view);
  const [selection, setSelection] = useState<{ kind: Kind; id: string } | null>(
    initialSelection,
  );
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [trail, setTrail] = useState<{ kind: Kind; id: string }[]>([]);
  const [editor, setEditor] = useState<Editor | null>(null);
  const [createPending, setCreatePending] = useState(initialCreate);
  const can = (permission: string) => user.permissions.includes(permission);
  const loadOwners = can("workspace_demand:view") || can("vacancy:edit");
  const owners = useQuery({
    queryKey: ["demand", "owners"],
    queryFn: () => api<{ items: Owner[] }>("/demand/owners"),
    enabled: loadOwners,
  });
  const references = useQuery({
    queryKey: ["demand", "references"],
    queryFn: () =>
      api<Record<string, { value: string; label: string }[]>>(
        "/demand/reference-data",
      ),
  });
  const employerOptions = useQuery({
    queryKey: ["demand", "employer-options"],
    queryFn: () => all<DemandRecord>("/organizations"),
    enabled: can("vacancy:create") && can("organization:view"),
  });
  function fieldsWithOwners(fields: Field[], vacancy = false): Field[] {
    return fields.map((field) => {
      if (
        ["owner_id", "relationship_owner_id", "demand_owner_id"].includes(
          field.key,
        )
      ) {
        return {
          ...field,
          options:
            owners.data?.items
              .filter((owner) =>
                vacancy && field.key === "owner_id"
                  ? owner.recruiter
                  : owner.demand,
              )
              .map((owner) => ({ value: owner.id, label: owner.full_name })) ??
            [],
        };
      }
      if (field.key === "priority")
        return { ...field, options: references.data?.priority ?? [] };
      if (field.key === "salary_frequency")
        return { ...field, options: references.data?.salary_frequency ?? [] };
      return field;
    });
  }
  const employer = fieldsWithOwners(employerFields);
  const vacancy = fieldsWithOwners(vacancyFields, true);
  const partnership = fieldsWithOwners(partnershipFields);
  const referencesUnavailable =
    (loadOwners && (owners.isPending || !!owners.error)) ||
    references.isPending ||
    !!references.error ||
    (can("vacancy:create") &&
      can("organization:view") &&
      (employerOptions.isPending || !!employerOptions.error));
  useEffect(() => {
    if (!createPending || referencesUnavailable) return;
    setCreatePending(false);
    if (
      view === "employers" &&
      user.permissions.includes("organization:create") &&
      user.permissions.includes("organization:view")
    )
      setEditor(employerEditor(employer, user));
    if (
      view === "vacancies" &&
      user.permissions.includes("vacancy:create") &&
      user.permissions.includes("vacancy:view")
    )
      setEditor(vacancyEditor(vacancy, employerOptions.data ?? [], user));
  }, [
    createPending,
    referencesUnavailable,
    view,
    user,
    employer,
    vacancy,
    employerOptions.data,
  ]);
  async function saved(row: Record<string, unknown>) {
    await client.invalidateQueries({ queryKey: ["demand"] });
    setEditor(null);
    if (editor?.title === "New employer")
      setSelection({ kind: "employers", id: String(row.id) });
    if (editor?.title === "New vacancy")
      setSelection({ kind: "vacancies", id: String(row.id) });
  }
  function open(kind: Kind, id: string) {
    if (selection) setTrail([...trail, selection]);
    setSelection({ kind, id });
  }
  function createVacancy(organizationId?: string) {
    setEditor(
      vacancyEditor(vacancy, employerOptions.data ?? [], user, organizationId),
    );
  }
  return (
    <div className="min-w-0">
      {createPending && referencesUnavailable && (
        <div className="mb-5 flex items-center justify-between gap-3 border-b border-border pb-4">
          {!(owners.error || references.error || employerOptions.error) && (
            <p role="status" className="text-sm text-muted">
              Loading form...
            </p>
          )}
          <button
            type="button"
            className="command"
            onClick={() => setCreatePending(false)}
          >
            Cancel
          </button>
        </div>
      )}
      {(owners.error || references.error || employerOptions.error) && (
        <div className="mb-5 flex items-center justify-between gap-3 border-b border-border pb-4">
          <p role="alert" className="text-sm text-red-700">
            Staff or reference data is unavailable.
          </p>
          <button
            className="icon-button"
            title="Retry reference data"
            aria-label="Retry reference data"
            onClick={() =>
              void client.invalidateQueries({ queryKey: ["demand"] })
            }
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      )}
      {selection ? (
        <RecordDetail
          key={selection.kind + selection.id}
          selection={selection}
          user={user}
          employerFields={employer}
          vacancyFields={vacancy}
          partnershipFields={partnership}
          blocked={referencesUnavailable}
          closureReasons={references.data?.closure_reason ?? []}
          onBack={() => {
            setSelection(trail[trail.length - 1] ?? null);
            setTrail(trail.slice(0, -1));
          }}
          onOpen={open}
          onEditor={setEditor}
          onVacancy={createVacancy}
        />
      ) : screen === "dashboard" ? (
        <Dashboard
          onOpen={(metric) => {
            setScreen(metric.resource);
            setFilters(metric.filters);
          }}
          onEmployer={(id) => open("employers", id)}
        />
      ) : screen === "work" ? (
        <MyWork onOpen={(id) => open("employers", id)} />
      ) : (
        <RecordList
          key={screen + JSON.stringify(filters)}
          kind={screen as Kind}
          user={user}
          initialFilters={filters}
          onOpen={open}
          onVacancyCreate={() => createVacancy()}
          onCreate={() => setEditor(employerEditor(employer, user))}
          blocked={referencesUnavailable}
        />
      )}
      {editor && (
        <DemandForm
          editor={editor}
          onClose={() => setEditor(null)}
          onSaved={saved}
          onReview={async () => {
            await client.invalidateQueries({ queryKey: ["demand"] });
            setEditor(null);
          }}
        />
      )}
    </div>
  );
}

function Dashboard({
  onOpen,
  onEmployer,
}: {
  onOpen: (metric: Metric) => void;
  onEmployer: (id: string) => void;
}) {
  const query = useQuery({
    queryKey: ["demand", "dashboard"],
    queryFn: () => api<{ metrics: Metric[] }>("/demand/dashboard"),
  });
  return (
    <>
      <div className="mb-6 flex items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">Demand Dashboard</h2>
        <Refresh onClick={() => void query.refetch()} />
      </div>
      <Feedback pending={query.isPending} error={query.error} />
      {query.data && (
        <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
          {query.data.metrics.map((metric) => (
            <button
              key={metric.code}
              onClick={() => onOpen(metric)}
              title={metric.code}
              className="metric-card"
            >
              <span className="block text-sm text-muted">{metric.label}</span>
              <strong className="mt-3 block text-2xl font-semibold">
                {metric.value.toLocaleString()}
              </strong>
              <ArrowRight
                className="mt-2 h-4 w-4 text-muted"
                aria-hidden="true"
              />
            </button>
          ))}
        </div>
      )}
      <section className="mt-9">
        <h3 className="text-base font-semibold">Needs attention</h3>
        <Attention onOpen={onEmployer} />
      </section>
    </>
  );
}
function Attention({ onOpen }: { onOpen: (id: string) => void }) {
  const query = useQuery({
    queryKey: ["demand", "attention"],
    queryFn: () => all<DemandRecord>("/organizations?status=MOU_PENDING"),
  });
  return (
    <>
      <Feedback pending={query.isPending} error={query.error} />
      {query.data?.map((row) => (
        <button
          key={row.id}
          className="data-row flex w-full items-center justify-between gap-3 text-left"
          onClick={() => onOpen(row.id)}
        >
          <span className="min-w-0 break-words text-sm font-medium">
            {row.name}
          </span>
          <span className="shrink-0 text-xs text-muted">MOU pending</span>
        </button>
      ))}
      {query.data?.length === 0 && (
        <p className="mt-4 border-y border-border py-8 text-sm text-muted">
          No pending MOUs
        </p>
      )}
    </>
  );
}
function MyWork({ onOpen }: { onOpen: (id: string) => void }) {
  const query = useQuery({
    queryKey: ["demand", "work"],
    queryFn: () => all<DemandRecord>("/demand/my-work"),
  });
  return (
    <>
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-xl font-semibold">My Work</h2>
        <Refresh onClick={() => void query.refetch()} />
      </div>
      <Feedback pending={query.isPending} error={query.error} />
      {[
        "Overdue",
        "Due today",
        "Upcoming",
        "High priority",
        "Recently assigned",
      ].map((bucket) => {
        const rows = query.data
          ?.filter((row) =>
            bucket === "High priority"
              ? ["HIGH", "URGENT"].includes(String(row.priority))
              : bucket === "Recently assigned"
                ? row.recently_assigned
                : row.bucket === bucket,
          )
          .sort((a, b) =>
            String(a.due_at ?? "9999").localeCompare(
              String(b.due_at ?? "9999"),
            ),
          );
        return (
          <section key={bucket} aria-label={bucket} className="mb-7">
            <h3 className="border-b border-border pb-3 text-sm font-semibold">
              {bucket}{" "}
              <span className="ml-2 text-muted">{rows?.length ?? 0}</span>
            </h3>
            {rows?.map((row) => (
              <button
                key={row.id}
                className="data-row flex w-full items-center justify-between gap-4 text-left"
                onClick={() => onOpen(String(row.organization_id))}
              >
                <span className="min-w-0">
                  <span className="block break-words text-sm font-medium">
                    {display(row.title)}
                  </span>
                  <span className="mt-1 block text-xs text-muted">
                    {row.organization_name} | {display(row.owner_name)} |{" "}
                    {label(row.priority)}
                  </span>
                </span>
                <span className="shrink-0 text-xs text-muted">
                  {row.due_at ? time(String(row.due_at)) : "No due date"}
                </span>
              </button>
            ))}
            {rows?.length === 0 && (
              <p className="py-6 text-sm text-muted">No assigned actions</p>
            )}
          </section>
        );
      })}
    </>
  );
}

function RecordList({
  kind,
  user,
  initialFilters,
  onOpen,
  onCreate,
  onVacancyCreate,
  blocked,
}: {
  kind: Kind;
  user: Me;
  initialFilters: Record<string, string>;
  onOpen: (kind: Kind, id: string) => void;
  onCreate: () => void;
  onVacancyCreate: () => void;
  blocked: boolean;
}) {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState(initialFilters.status ?? "");
  const [cursor, setCursor] = useState<string | null>(null);
  const [previous, setPrevious] = useState<(string | null)[]>([]);
  const [mine, setMine] = useState(false);
  const [archived, setArchived] = useState(false);
  const [pipeline, setPipeline] = useState(false);
  const options =
    kind === "employers"
      ? [
          "ACTIVE",
          "MOU_PENDING",
          "INACTIVE",
          "LEAD",
          "CONTACTED",
          "ENGAGED",
          "INTERESTED",
          "MOU_SIGNED",
          "DECLINED",
        ]
      : [
          "DRAFT",
          "PENDING_CONFIRMATION",
          "ACTIVE",
          "PARTIALLY_FILLED",
          "ON_HOLD",
          "FULLY_FILLED",
          "CLOSED",
          "CANCELLED",
        ];
  const params = new URLSearchParams({
    ...initialFilters,
    q: search,
    ...(status ? { status } : {}),
    ...(cursor ? { cursor } : {}),
    ...(mine ? { owner_id: user.id } : {}),
    ...(archived ? { archived: "true" } : {}),
    ...(pipeline ? { pipeline_only: "true" } : {}),
  });
  if (!status) params.delete("status");
  const path = pathFor(kind) + "?" + params;
  const query = useQuery({
    queryKey: ["demand", "list", path],
    queryFn: () => api<DemandPage>(path),
  });
  const title = kind === "employers" ? "Employers" : "Vacancies";
  function reset() {
    setCursor(null);
    setPrevious([]);
  }
  return (
    <>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">{title}</h2>
        <div className="flex gap-2">
          <Refresh onClick={() => void query.refetch()} />
          {kind === "employers" &&
            user.permissions.includes("organization:create") && (
              <button
                className="command primary"
                disabled={blocked}
                onClick={onCreate}
              >
                <Plus className="h-4 w-4" />
                New employer
              </button>
            )}
          {kind === "vacancies" &&
            user.permissions.includes("vacancy:create") &&
            user.permissions.includes("organization:view") && (
              <button
                className="command primary"
                disabled={blocked}
                onClick={onVacancyCreate}
              >
                <Plus className="h-4 w-4" />
                New vacancy
              </button>
            )}
        </div>
      </div>
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <label className="relative min-w-0 flex-1 sm:max-w-sm">
          <span className="sr-only">Search {title.toLowerCase()}</span>
          <Search
            className="absolute left-3 top-3 h-4 w-4 text-muted"
            aria-hidden="true"
          />
          <input
            className="field pl-9"
            maxLength={200}
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              reset();
            }}
          />
        </label>
        <label className="min-w-0">
          <span className="sr-only">Status filter</span>
          <select
            className="field max-w-56 capitalize"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setPipeline(false);
              reset();
            }}
          >
            <option value="">All statuses</option>
            {options.map((value) => (
              <option key={value} value={value}>
                {label(value)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={mine}
            onChange={(event) => {
              setMine(event.target.checked);
              reset();
            }}
          />
          Assigned to me
        </label>
        {kind === "employers" && (
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={archived}
              onChange={(event) => {
                setArchived(event.target.checked);
                reset();
              }}
            />
            Archived
          </label>
        )}
      </div>
      <Feedback pending={query.isPending} error={query.error} />
      {kind === "employers" && (
        <div
          role="tablist"
          aria-label="Employer views"
          className="mb-5 flex flex-wrap gap-1 border-b border-border"
        >
          {["Pipeline", "Active", "MOU pending", "Inactive", "All"].map(
            (item) => {
              const current = pipeline
                ? "Pipeline"
                : status === "ACTIVE"
                  ? "Active"
                  : status === "MOU_PENDING"
                    ? "MOU pending"
                    : status === "INACTIVE"
                      ? "Inactive"
                      : !status
                        ? "All"
                        : null;
              return (
                <button
                  key={item}
                  role="tab"
                  aria-selected={current === item}
                  className={
                    "border-b-2 px-3 py-3 text-sm " +
                    (current === item
                      ? "border-primary font-medium text-primary"
                      : "border-transparent text-muted")
                  }
                  onClick={() => {
                    setPipeline(item === "Pipeline");
                    setStatus(
                      item === "Active"
                        ? "ACTIVE"
                        : item === "MOU pending"
                          ? "MOU_PENDING"
                          : item === "Inactive"
                            ? "INACTIVE"
                            : "",
                    );
                    reset();
                  }}
                >
                  {item}
                </button>
              );
            },
          )}
        </div>
      )}
      <div className="border-t border-border">
        {query.data?.items.map((row) => (
          <button
            key={row.id}
            className="data-row flex w-full items-start justify-between gap-4 text-left hover:bg-white"
            onClick={() => onOpen(kind, row.id)}
          >
            <span className="min-w-0">
              <span className="block break-words text-sm font-semibold">
                {row.name ?? row.title}
              </span>
              <span className="mt-1 block break-words text-xs text-muted">
                {kind === "employers"
                  ? display(row.organization_code)
                  : display(row.vacancy_code) + " | " + row.organization_name}
              </span>
              {row.headcount && (
                <span className="mt-2 block text-xs text-muted">
                  {row.headcount.outstanding} outstanding /{" "}
                  {row.headcount.required} required
                </span>
              )}
            </span>
            <span className="flex shrink-0 flex-col items-end gap-2">
              <span className="rounded border border-border bg-white px-2 py-1 text-xs capitalize">
                {row.archived_at ? "Archived" : label(row.status)}
              </span>
              {kind === "vacancies" && (
                <span className="text-xs capitalize text-muted">
                  {label(row.priority)}
                </span>
              )}
              <ChevronRight className="h-4 w-4 text-muted" />
            </span>
          </button>
        ))}
        {query.data?.items.length === 0 && (
          <div className="flex min-h-44 flex-col items-center justify-center gap-3 border-b border-border text-muted">
            {kind === "employers" ? (
              <Building2 className="h-6 w-6" />
            ) : (
              <ClipboardList className="h-6 w-6" />
            )}
            <p className="text-sm">No {title.toLowerCase()} found</p>
          </div>
        )}
      </div>
      <div className="mt-5 flex items-center justify-between gap-3 text-sm text-muted">
        <span>Page {previous.length + 1}</span>
        <div className="flex gap-2">
          <button
            className="icon-button"
            title="Previous page"
            aria-label="Previous page"
            disabled={!previous.length || query.isPending}
            onClick={() => {
              setCursor(previous[previous.length - 1]);
              setPrevious(previous.slice(0, -1));
            }}
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <button
            className="icon-button"
            title="Next page"
            aria-label="Next page"
            disabled={!query.data?.next_cursor || query.isPending}
            onClick={() => {
              setPrevious([...previous, cursor]);
              setCursor(query.data!.next_cursor);
            }}
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </>
  );
}

function RecordDetail({
  selection,
  user,
  employerFields,
  vacancyFields,
  partnershipFields,
  blocked,
  closureReasons,
  onBack,
  onOpen,
  onEditor,
  onVacancy,
}: {
  selection: { kind: Kind; id: string };
  user: Me;
  employerFields: Field[];
  vacancyFields: Field[];
  partnershipFields: Field[];
  blocked: boolean;
  closureReasons: { value: string; label: string }[];
  onBack: () => void;
  onOpen: (kind: Kind, id: string) => void;
  onEditor: (editor: Editor) => void;
  onVacancy: (id: string) => void;
}) {
  const { kind, id } = selection;
  const [tab, setTab] = useState("Overview");
  const path = pathFor(kind) + "/" + id;
  const query = useQuery({
    queryKey: ["demand", "detail", path],
    queryFn: () => api<DemandRecord>(path),
  });
  const row = query.data;
  const can = (permission: string) => user.permissions.includes(permission);
  const editable =
    can(kind === "employers" ? "organization:edit" : "vacancy:edit") &&
    !row?.archived_at;
  const tabs =
    kind === "employers"
      ? [
          "Overview",
          ...(can("organization_contact:view") ? ["Contacts"] : []),
          ...(can("partnership:view") ? ["Partnership / MOU"] : []),
          ...(can("vacancy:view") ? ["Vacancies"] : []),
          "Activity",
        ]
      : [
          "Overview",
          ...(can("organization:view") ? ["Employer"] : []),
          ...(can("job_description:view") ? ["Job descriptions"] : []),
          "Requirements",
          "Changes",
          "Activity",
        ];
  const fields = kind === "employers" ? employerFields : vacancyFields;
  return (
    <>
      <button
        className="mb-5 flex items-center gap-2 text-sm text-muted hover:text-primary"
        onClick={onBack}
      >
        <ArrowLeft className="h-4 w-4" />
        Back
      </button>
      <Feedback pending={query.isPending} error={query.error} />
      {row && (
        <>
          <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="mb-2 text-xs text-muted">
                {display(row.organization_code ?? row.vacancy_code)}
              </p>
              <h2 className="break-words text-xl font-semibold">
                {row.name ?? row.title}
              </h2>
              <p className="mt-2 text-sm capitalize text-muted">
                {label(row.status)}
                {row.archived_at ? " | Archived" : ""}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Refresh onClick={() => void query.refetch()} />
              {editable && (
                <button
                  className="command"
                  disabled={blocked}
                  onClick={() =>
                    onEditor({
                      title:
                        kind === "employers" ? "Edit employer" : "Edit vacancy",
                      path,
                      method: "PATCH",
                      fields:
                        kind === "employers"
                          ? fields
                          : [...fields, reasonField],
                      initial: row,
                      extra: { version: row.version },
                    })
                  }
                >
                  <Pencil className="h-4 w-4" />
                  Edit
                </button>
              )}
              {kind === "employers" &&
                !row.archived_at &&
                can("vacancy:create") && (
                  <button
                    className="command primary"
                    disabled={blocked}
                    onClick={() => onVacancy(id)}
                  >
                    <Plus className="h-4 w-4" />
                    New vacancy
                  </button>
                )}
              {kind === "employers" && editable && (
                <button
                  className="icon-button"
                  title="Archive employer"
                  aria-label="Archive employer"
                  onClick={() =>
                    onEditor({
                      title: "Archive employer",
                      path: path + "/archive",
                      fields: [reasonField],
                      extra: { version: row.version },
                    })
                  }
                >
                  <Archive className="h-4 w-4" />
                </button>
              )}
              {kind === "vacancies" &&
                editable &&
                row.allowed_transitions?.length !== 0 && (
                  <button
                    className="command"
                    onClick={() =>
                      onEditor({
                        title: "Change vacancy status",
                        path: path + "/transition",
                        fields: [
                          {
                            key: "to_status",
                            label: "Next status",
                            type: "select",
                            required: true,
                            options: row.allowed_transitions?.map((value) => ({
                              value,
                              label: label(value),
                            })),
                          },
                          {
                            key: "closure_reason",
                            label: "Closure reason",
                            type: "select",
                            options: closureReasons,
                          },
                          reasonField,
                          {
                            key: "closure_note",
                            label: "Closure note",
                            type: "textarea",
                            max: 5000,
                          },
                        ],
                        extra: { version: row.version },
                      })
                    }
                  >
                    <ArrowRight className="h-4 w-4" />
                    Change status
                  </button>
                )}
            </div>
          </div>
          {row.headcount && (
            <div className="mb-6 grid grid-cols-2 gap-5 border-y border-border py-4 sm:grid-cols-4">
              {Object.entries(row.headcount).map(([key, value]) => (
                <div key={key}>
                  <p className="text-xs capitalize text-muted">{label(key)}</p>
                  <p className="mt-1 text-lg font-semibold">{value}</p>
                </div>
              ))}
            </div>
          )}
          <div
            role="tablist"
            aria-label="Record sections"
            className="mb-6 flex flex-wrap gap-1 border-b border-border"
          >
            {tabs.map((item) => (
              <button
                role="tab"
                aria-selected={tab === item}
                key={item}
                onClick={() => setTab(item)}
                className={
                  "border-b-2 px-3 py-3 text-sm " +
                  (tab === item
                    ? "border-primary font-medium text-primary"
                    : "border-transparent text-muted")
                }
              >
                {item}
              </button>
            ))}
          </div>
          <div role="tabpanel" aria-label={tab}>
            {tab === "Overview" && <Details fields={fields} row={row} />}
            {tab === "Employer" && (
              <button
                className="command"
                onClick={() => onOpen("employers", String(row.organization_id))}
              >
                <Building2 className="h-4 w-4" />
                {row.organization_name}
              </button>
            )}
            {tab === "Contacts" && (
              <Contacts
                path={path + "/contacts"}
                canEdit={can("organization_contact:edit") && !row.archived_at}
                onEditor={onEditor}
              />
            )}
            {tab === "Partnership / MOU" && (
              <PartnershipSection
                path={path + "/partnership"}
                fields={partnershipFields}
                canEdit={can("partnership:edit") && !row.archived_at}
                canViewDocuments={can("partnership_document:view")}
                canEditDocuments={can("partnership_document:edit")}
                canDownloadDocuments={can("partnership_document:download")}
                blocked={blocked}
                onEditor={onEditor}
              />
            )}
            {tab === "Vacancies" && (
              <RelatedVacancies employerId={id} onOpen={onOpen} />
            )}
            {tab === "Requirements" && (
              <Requirements
                path={path + "/requirements"}
                vacancy={row}
                canEdit={editable}
                onEditor={onEditor}
              />
            )}
            {tab === "Job descriptions" && (
              <PrivateDocuments
                path={path + "/job-descriptions"}
                downloadBase="/job-descriptions"
                ownerVersion={row.version}
                canEdit={can("job_description:edit") && !row.archived_at}
                canDownload={can("job_description:download")}
              />
            )}
            {(tab === "Changes" || tab === "Activity") && (
              <History
                path={path + (tab === "Changes" ? "/changes" : "/activity")}
                changes={tab === "Changes"}
              />
            )}
          </div>
        </>
      )}
    </>
  );
}
function Contacts({
  path,
  canEdit,
  onEditor,
}: {
  path: string;
  canEdit: boolean;
  onEditor: (editor: Editor) => void;
}) {
  const query = useQuery({
    queryKey: ["demand", "contacts", path],
    queryFn: () => all<DemandRecord>(path),
  });
  return (
    <>
      <div className="mb-4 flex justify-end gap-2">
        <Refresh onClick={() => void query.refetch()} />
        {canEdit && (
          <button
            className="command"
            onClick={() =>
              onEditor({
                title: "New contact",
                path,
                fields: contactFields,
                initial: { is_active: true },
              })
            }
          >
            <Plus className="h-4 w-4" />
            New contact
          </button>
        )}
      </div>
      <Feedback pending={query.isPending} error={query.error} />
      {query.data?.map((row) => (
        <div
          className="data-row flex items-start justify-between gap-4"
          key={row.id}
        >
          <div className="min-w-0">
            <p className="break-words text-sm font-medium">
              {display(row.full_name)} {row.is_primary ? "(primary)" : ""}
            </p>
            <p className="mt-1 break-words text-xs text-muted">
              {display(row.job_title)} | {row.is_active ? "Active" : "Inactive"}
            </p>
            <p className="mt-2 break-words text-sm">
              {display(row.phone_normalized)} | {display(row.email)}
            </p>
            {row.notes ? (
              <p className="mt-2 whitespace-pre-wrap break-words text-sm text-muted">
                {display(row.notes)}
              </p>
            ) : null}
          </div>
          {canEdit && (
            <button
              className="icon-button"
              title="Edit contact"
              aria-label={"Edit " + display(row.full_name)}
              onClick={() =>
                onEditor({
                  title: "Edit contact",
                  path: "/organization-contacts/" + row.id,
                  method: "PATCH",
                  fields: contactFields,
                  initial: row,
                  extra: { version: row.version },
                })
              }
            >
              <Pencil className="h-4 w-4" />
            </button>
          )}
        </div>
      ))}
      {query.data?.length === 0 && (
        <p className="border-y border-border py-8 text-sm text-muted">
          No contacts recorded
        </p>
      )}
    </>
  );
}
function PartnershipSection({
  path,
  fields,
  canEdit,
  canViewDocuments,
  canEditDocuments,
  canDownloadDocuments,
  blocked,
  onEditor,
}: {
  path: string;
  fields: Field[];
  canEdit: boolean;
  canViewDocuments: boolean;
  canEditDocuments: boolean;
  canDownloadDocuments: boolean;
  blocked: boolean;
  onEditor: (editor: Editor) => void;
}) {
  const query = useQuery({
    queryKey: ["demand", "partnership", path],
    queryFn: () => api<DemandRecord>(path),
  });
  const history = useQuery({
    queryKey: ["demand", "partnership-history", path],
    queryFn: () => all<DemandRecord>(path + "s"),
  });
  const row = query.data;
  return (
    <>
      <Feedback pending={query.isPending} error={query.error} />
      {row && (
        <>
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <h3 className="text-sm font-semibold capitalize">
              {label(row.status)}
            </h3>
            <div className="flex gap-2">
              <Refresh onClick={() => void query.refetch()} />
              {canEdit && (
                <>
                  <button
                    className="command"
                    disabled={blocked}
                    onClick={() =>
                      onEditor({
                        title: "New partnership period",
                        path,
                        fields: fields.filter(
                          (field) => field.key !== "reason",
                        ),
                        initial: {
                          partnership_type: "RECRUITMENT",
                          start_date: new Date().toISOString().slice(0, 10),
                          mou_required: true,
                          priority: "NORMAL",
                        },
                      })
                    }
                  >
                    <Plus className="h-4 w-4" />
                    New period
                  </button>
                  <button
                    className="command"
                    disabled={blocked}
                    onClick={() =>
                      onEditor({
                        title: "Edit partnership",
                        path: "/partnerships/" + row.id,
                        method: "PATCH",
                        fields,
                        initial: row,
                        extra: { version: row.version },
                      })
                    }
                  >
                    <Pencil className="h-4 w-4" />
                    Edit partnership
                  </button>
                  {!!row.allowed_transitions?.length && (
                    <button
                      className="command primary"
                      onClick={() =>
                        onEditor({
                          title: "Change relationship status",
                          path: "/partnerships/" + row.id + "/transition",
                          fields: [
                            {
                              key: "to_status",
                              label: "Next status",
                              type: "select",
                              required: true,
                              options: row.allowed_transitions?.map(
                                (value) => ({ value, label: label(value) }),
                              ),
                            },
                            {
                              ...reasonField,
                              required: row.status === "INACTIVE",
                            },
                          ],
                          extra: { version: row.version },
                        })
                      }
                    >
                      <ArrowRight className="h-4 w-4" />
                      Change status
                    </button>
                  )}
                </>
              )}
            </div>
          </div>
          <Details
            fields={fields.map((field) =>
              field.type === "datetime-local"
                ? { ...field, type: "text" }
                : field,
            )}
            row={{
              ...row,
              mou_sent_at: row.mou_sent_at
                ? time(String(row.mou_sent_at))
                : null,
              mou_signed_at: row.mou_signed_at
                ? time(String(row.mou_signed_at))
                : null,
              next_action_due_at: row.next_action_due_at
                ? time(String(row.next_action_due_at))
                : null,
            }}
          />
          {canViewDocuments && (
            <div className="mt-6 border-t border-border pt-5">
              <h4 className="mb-3 text-sm font-semibold">Agreement versions</h4>
              <PrivateDocuments
                path={`/partnerships/${row.id}/documents`}
                downloadBase="/partnership-documents"
                ownerVersion={row.version}
                canEdit={canEdit && canEditDocuments}
                canDownload={canDownloadDocuments}
              />
            </div>
          )}
          <div className="mt-6 border-t border-border pt-5">
            <h4 className="mb-3 text-sm font-semibold">Partnership history</h4>
            <Feedback pending={history.isPending} error={history.error} />
            {history.data?.map((period) => (
              <div className="data-row" key={period.id}>
                <p className="text-sm font-medium">
                  {label(period.partnership_type)} · {label(period.status)}
                </p>
                <p className="mt-1 text-xs text-muted">
                  {display(period.start_date)} to{" "}
                  {display(period.end_date ?? "Present")}
                </p>
              </div>
            ))}
          </div>
        </>
      )}
    </>
  );
}

function PrivateDocuments({
  path,
  downloadBase,
  ownerVersion,
  canEdit,
  canDownload,
}: {
  path: string;
  downloadBase: string;
  ownerVersion: number;
  canEdit: boolean;
  canDownload: boolean;
}) {
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const query = useQuery({
    queryKey: ["demand", "private-documents", path],
    queryFn: () => all<DemandRecord>(path),
  });
  async function upload(file: File) {
    setBusy(true);
    setError("");
    const body = new FormData();
    body.set("version", String(ownerVersion));
    body.set("file", file);
    try {
      await api(path, "POST", body);
      await Promise.all([
        query.refetch(),
        client.invalidateQueries({ queryKey: ["demand", "detail"] }),
        client.invalidateQueries({ queryKey: ["demand", "partnership"] }),
      ]);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Unable to upload document.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function rescan(row: DemandRecord) {
    setBusy(true);
    setError("");
    try {
      await api(`${downloadBase}/${row.id}/rescan`, "POST", {
        version: row.version,
      });
      await query.refetch();
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Unable to rescan document.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function download(row: DemandRecord) {
    setError("");
    try {
      await downloadGet(`${downloadBase}/${row.id}/download`);
    } catch (reason) {
      setError(
        reason instanceof ApiError
          ? reason.message
          : "Unable to download document.",
      );
    }
  }
  return (
    <>
      <div className="mb-4 flex justify-end gap-2">
        <Refresh onClick={() => void query.refetch()} />
        {canEdit && (
          <label className="command cursor-pointer">
            <Upload className="h-4 w-4" />
            Upload version
            <input
              className="sr-only"
              type="file"
              accept=".pdf,.docx"
              disabled={busy}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) void upload(file);
                event.target.value = "";
              }}
            />
          </label>
        )}
      </div>
      <Feedback pending={query.isPending || busy} error={query.error} />
      {error && (
        <p role="alert" className="mb-3 text-sm text-red-700">
          {error}
        </p>
      )}
      {query.data?.map((row) => (
        <div
          className="data-row flex items-center justify-between gap-3"
          key={row.id}
        >
          <div className="min-w-0">
            <p className="break-words text-sm font-medium">
              Version {display(row.version_number)} ·{" "}
              {display(row.original_filename)}
            </p>
            <p className="mt-1 text-xs text-muted">{label(row.scan_status)}</p>
          </div>
          <div className="flex gap-2">
            {canEdit && row.scan_status === "SCANNING" && (
              <button
                className="icon-button"
                title="Retry scan"
                aria-label={`Retry scan for ${display(row.original_filename)}`}
                disabled={busy}
                onClick={() => void rescan(row)}
              >
                <RefreshCw className="h-4 w-4" />
              </button>
            )}
            {canDownload && row.scan_status === "AVAILABLE" && (
              <button
                className="icon-button"
                title="Download"
                aria-label={`Download ${display(row.original_filename)}`}
                onClick={() => void download(row)}
              >
                <Download className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>
      ))}
      {query.data?.length === 0 && (
        <p className="border-y border-border py-8 text-sm text-muted">
          No document versions recorded
        </p>
      )}
    </>
  );
}
function RelatedVacancies({
  employerId,
  onOpen,
}: {
  employerId: string;
  onOpen: (kind: Kind, id: string) => void;
}) {
  const query = useQuery({
    queryKey: ["demand", "related", employerId],
    queryFn: () =>
      all<DemandRecord>("/vacancies?organization_id=" + employerId),
  });
  return (
    <>
      <Feedback pending={query.isPending} error={query.error} />
      {query.data?.map((row) => (
        <button
          key={row.id}
          className="data-row flex w-full items-center justify-between gap-3 text-left"
          onClick={() => onOpen("vacancies", row.id)}
        >
          <span className="min-w-0 break-words text-sm font-medium">
            {row.title}
          </span>
          <span className="text-xs capitalize text-muted">
            {label(row.status)}
          </span>
        </button>
      ))}
      {query.data?.length === 0 && (
        <p className="py-8 text-sm text-muted">No vacancies recorded</p>
      )}
    </>
  );
}
function Requirements({
  path,
  vacancy,
  canEdit,
  onEditor,
}: {
  path: string;
  vacancy: DemandRecord;
  canEdit: boolean;
  onEditor: (editor: Editor) => void;
}) {
  const query = useQuery({
    queryKey: ["demand", "requirements", path],
    queryFn: () => all<DemandRecord>(path),
  });
  return (
    <>
      <div className="mb-4 flex justify-end gap-2">
        <Refresh onClick={() => void query.refetch()} />
        {canEdit && (
          <button
            className="command"
            onClick={() =>
              onEditor({
                title: "New requirement",
                path,
                fields: requirementFields,
                initial: {
                  operator: "EQ",
                  is_required: true,
                  weight: 1,
                  display_order: 0,
                },
                extra: { version: vacancy.version },
              })
            }
          >
            <Plus className="h-4 w-4" />
            New requirement
          </button>
        )}
      </div>
      <Feedback pending={query.isPending} error={query.error} />
      {query.data
        ?.sort((a, b) => Number(a.display_order) - Number(b.display_order))
        .map((row) => (
          <div
            key={row.id}
            className="data-row flex items-start justify-between gap-4"
          >
            <div className="min-w-0">
              <p className="break-words text-sm font-medium">
                {display(row.criterion_key)}
              </p>
              <p className="mt-1 break-words text-sm">
                {display(row.operator)} {display(row.value_json)}
              </p>
              <p className="mt-1 text-xs text-muted">
                {row.is_required ? "Required" : "Preferred"} | Weight{" "}
                {display(row.weight)}
              </p>
            </div>
            {canEdit && (
              <div className="flex shrink-0 gap-1">
                <button
                  className="icon-button"
                  title="Edit requirement"
                  aria-label={"Edit " + display(row.criterion_key)}
                  onClick={() =>
                    onEditor({
                      title: "Edit requirement",
                      path: "/vacancy-requirements/" + row.id,
                      method: "PATCH",
                      fields: requirementFields,
                      initial: row,
                      extra: { version: vacancy.version },
                    })
                  }
                >
                  <Pencil className="h-4 w-4" />
                </button>
                <button
                  className="icon-button"
                  title="Archive requirement"
                  aria-label={"Archive " + display(row.criterion_key)}
                  onClick={() =>
                    onEditor({
                      title: "Archive requirement",
                      path: "/vacancy-requirements/" + row.id + "/archive",
                      fields: [reasonField],
                      extra: { version: vacancy.version },
                    })
                  }
                >
                  <Archive className="h-4 w-4" />
                </button>
              </div>
            )}
          </div>
        ))}
      {query.data?.length === 0 && (
        <p className="py-8 text-sm text-muted">No requirements recorded</p>
      )}
    </>
  );
}
function History({ path, changes }: { path: string; changes: boolean }) {
  const query = useQuery({
    queryKey: ["demand", "history", path],
    queryFn: () => all<DemandRecord>(path),
  });
  return (
    <>
      <div className="mb-4 flex justify-end">
        <Refresh onClick={() => void query.refetch()} />
      </div>
      <Feedback pending={query.isPending} error={query.error} />
      {query.data
        ?.sort((a, b) =>
          String(b.changed_at ?? b.occurred_at).localeCompare(
            String(a.changed_at ?? a.occurred_at),
          ),
        )
        .map((row) => (
          <div key={row.id} className="data-row min-w-0">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="break-words text-sm font-medium">
                {changes
                  ? changeLabel(row.field_name)
                  : display(row.event_code)
                      .replaceAll("_", " ")
                      .replace(".", ": ")}
              </p>
              <p className="text-xs text-muted">
                {time(String(row.changed_at ?? row.occurred_at))}
              </p>
            </div>
            {changes && (
              <p className="mt-2 break-words text-sm">
                <span className="text-muted">
                  {changeValue(row.old_value_json, String(row.field_name))}
                </span>{" "}
                <ArrowRight className="inline h-3 w-3" />{" "}
                {changeValue(row.new_value_json, String(row.field_name))}
              </p>
            )}
            {row.reason ? (
              <p className="mt-2 break-words text-sm text-muted">
                {display(row.reason)}
              </p>
            ) : null}
          </div>
        ))}
      {query.data?.length === 0 && (
        <p className="py-8 text-sm text-muted">No history recorded</p>
      )}
    </>
  );
}

function changeLabel(value: unknown) {
  const key = String(value);
  if (key.startsWith("requirement:")) return "Requirement";
  return vacancyFields.find((field) => field.key === key)?.label ?? label(key);
}
function changeValue(value: unknown, field: string): string {
  if (value && typeof value === "object" && "criterion_key" in value) {
    const criterion = value as Record<string, unknown>;
    return (
      label(criterion.criterion_key) +
      " " +
      display(criterion.operator) +
      " " +
      display(criterion.value_json)
    );
  }
  if (field === "status") return label(value);
  if (
    field.startsWith("salary_") &&
    value !== null &&
    value !== "" &&
    Number.isFinite(Number(value))
  ) {
    return Number(value).toLocaleString("en-GH", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }
  return display(value);
}
