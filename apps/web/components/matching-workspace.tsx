"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarDays,
  Check,
  ChevronRight,
  Columns3,
  List,
  Plus,
  RefreshCw,
  Search,
  UserRoundCheck,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { all, api, Me, time } from "@/lib/api";
import { DemandRecord, Field } from "@/lib/demand";
import {
  Candidate,
  candidateFields,
  Interview,
  interviewFields,
  label,
  Option,
  screeningFields,
  stages,
} from "@/lib/matching";
import { DemandForm, Editor } from "./demand-form";

type History = {
  id: string;
  from_status: string | null;
  to_status: string;
  reason: string | null;
  occurred_at: string;
};
type Dashboard = {
  metrics: { label: string; value: number; status: string }[];
  submission_conversion: {
    numerator: number;
    denominator: number;
    rate: number | null;
  };
  interview_conversion: {
    numerator: number | null;
    denominator: number;
    rate: number | null;
  };
};
type Screening = {
  id: string;
  result: string;
  participant_interested: boolean;
  availability_confirmed: boolean;
  notes: string | null;
  created_at: string;
};
type Decision = {
  id: string;
  decision: string;
  reason: string;
  created_at: string;
};
type InterviewHistory = {
  id: string;
  from_status: string | null;
  to_status: string;
  scheduled_at: string;
  reason: string | null;
  occurred_at: string;
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
        Loading matching records...
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

function Refresh({ action }: { action: () => void }) {
  return (
    <button
      className="icon-button"
      title="Refresh"
      aria-label="Refresh"
      onClick={action}
    >
      <RefreshCw className="h-4 w-4" />
    </button>
  );
}

export function MatchingWorkspace({ view, user }: { view: string; user: Me }) {
  const client = useQueryClient();
  const [screen, setScreen] = useState(view);
  const [selected, setSelected] = useState<string | null>(null);
  const [editor, setEditor] = useState<Editor | null>(null);
  const [pipelineStatus, setPipelineStatus] = useState("");
  const owners = useQuery({
    queryKey: ["matching", "owners"],
    queryFn: () => api<Option[]>("/matching/owners"),
  });
  async function saved(row: Record<string, unknown>) {
    await client.invalidateQueries({ queryKey: ["matching"] });
    setEditor(null);
    if (row.id && editor?.path === "/candidate-vacancies")
      setSelected(String(row.id));
  }
  return (
    <div className="min-w-0">
      {selected ? (
        <CandidateDetail
          id={selected}
          user={user}
          owners={owners.data ?? []}
          onBack={() => setSelected(null)}
          onEditor={setEditor}
        />
      ) : screen === "dashboard" ? (
        <MatchingDashboard
          onOpen={(status) => {
            setPipelineStatus(status);
            setScreen("pipeline");
          }}
        />
      ) : screen === "interviews" ? (
        <InterviewDay
          user={user}
          onCandidate={setSelected}
          onEditor={setEditor}
        />
      ) : screen === "work" ? (
        <MyMatchingWork onOpen={setSelected} />
      ) : (
        <Pipeline
          user={user}
          initialStatus={pipelineStatus}
          owners={owners.data ?? []}
          onOpen={setSelected}
          onEditor={setEditor}
        />
      )}
      {editor?.path && (
        <DemandForm
          editor={editor}
          onClose={() => setEditor(null)}
          onSaved={saved}
          onReview={async () => {
            await client.invalidateQueries({ queryKey: ["matching"] });
            setEditor(null);
          }}
        />
      )}
    </div>
  );
}

function MatchingDashboard({ onOpen }: { onOpen: (status: string) => void }) {
  const query = useQuery({
    queryKey: ["matching", "dashboard"],
    queryFn: () => api<Dashboard>("/matching/dashboard"),
  });
  return (
    <>
      <div className="mb-6 flex items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">Matching Dashboard</h2>
        <Refresh action={() => void query.refetch()} />
      </div>
      <Feedback pending={query.isPending} error={query.error} />
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        {query.data?.metrics.map((metric) => (
          <button
            key={metric.status}
            className="metric-card text-left"
            onClick={() => onOpen(metric.status)}
          >
            <span className="block text-sm text-muted">{metric.label}</span>
            <strong className="mt-3 block text-2xl font-semibold">
              {metric.value}
            </strong>
            <ChevronRight className="mt-2 h-4 w-4 text-muted" />
          </button>
        ))}
      </div>
      {query.data && (
        <div className="mt-8 grid gap-6 border-y border-border py-5 sm:grid-cols-2">
          {[
            {
              name: "Qualified to submitted",
              value: query.data.submission_conversion,
            },
            {
              name: "Submitted to interviewed",
              value: query.data.interview_conversion,
            },
          ].map((item) => (
            <div key={item.name}>
              <p className="text-sm text-muted">{item.name}</p>
              <p className="mt-2 text-xl font-semibold">
                {item.value.rate === null
                  ? "Not available"
                  : item.value.rate + "%"}
              </p>
              <p className="mt-1 text-xs text-muted">
                {item.value.numerator ?? 0} of {item.value.denominator}
              </p>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function Pipeline({
  user,
  initialStatus,
  owners,
  onOpen,
  onEditor,
}: {
  user: Me;
  initialStatus: string;
  owners: Option[];
  onOpen: (id: string) => void;
  onEditor: (value: Editor) => void;
}) {
  const [mode, setMode] = useState<"pipeline" | "table">("pipeline");
  const [status, setStatus] = useState(initialStatus);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [bulkTarget, setBulkTarget] = useState("");
  const [bulkReason, setBulkReason] = useState("");
  const [bulkError, setBulkError] = useState("");
  const [bulkBusy, setBulkBusy] = useState(false);
  const client = useQueryClient();
  const canEdit = user.permissions.includes("candidate_pipeline:edit");
  useEffect(() => setStatus(initialStatus), [initialStatus]);
  const query = useQuery({
    queryKey: ["matching", "pipeline", status, search],
    queryFn: () => {
      const params = new URLSearchParams();
      if (status) params.set("status", status);
      if (search) params.set("q", search);
      const suffix = params.size ? "?" + params : "";
      return all<Candidate>("/candidate-vacancies" + suffix);
    },
  });
  const participants = useQuery({
    queryKey: ["matching", "participants"],
    queryFn: () => all<DemandRecord>("/participants"),
    enabled: canEdit,
  });
  const vacancies = useQuery({
    queryKey: ["matching", "vacancies"],
    queryFn: () => all<DemandRecord>("/vacancies?status=ACTIVE"),
    enabled: canEdit,
  });
  const selectedRows = (query.data ?? []).filter((row) =>
    selected.includes(row.id),
  );
  const bulkTargets = selectedRows.length
    ? selectedRows[0].allowed_transitions.filter((target) =>
        selectedRows.every((row) => row.allowed_transitions.includes(target)),
      )
    : [];
  const toggle = (id: string) =>
    setSelected((current) =>
      current.includes(id)
        ? current.filter((value) => value !== id)
        : current.length < 25
          ? [...current, id]
          : current,
    );
  const runBulk = async () => {
    if (!bulkTarget || !selectedRows.length) return;
    setBulkBusy(true);
    setBulkError("");
    try {
      await api("/candidate-vacancies/bulk-transition", "POST", {
        candidates: selectedRows.map((row) => ({
          id: row.id,
          version: row.version,
        })),
        to_status: bulkTarget,
        reason: bulkReason || null,
      });
      setSelected([]);
      setBulkTarget("");
      setBulkReason("");
      await client.invalidateQueries({ queryKey: ["matching"] });
    } catch (error) {
      setBulkError(
        error instanceof Error ? error.message : "Bulk update failed.",
      );
    } finally {
      setBulkBusy(false);
    }
  };
  const create = () =>
    onEditor({
      title: "Add candidate to vacancy",
      path: "/candidate-vacancies",
      fields: [
        {
          key: "participant_id",
          label: "Participant",
          type: "select",
          required: true,
          options: (participants.data ?? []).map((row) => ({
            value: row.id,
            label: String(row.full_name ?? row.participant_code),
          })),
        },
        {
          key: "vacancy_id",
          label: "Vacancy",
          type: "select",
          required: true,
          options: (vacancies.data ?? []).map((row) => ({
            value: row.id,
            label: String(row.title) + " | " + String(row.organization_name),
          })),
        },
        ...candidateFields(owners),
      ],
      initial: { owner_id: user.id, priority: "NORMAL" },
    });
  return (
    <>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">Candidate Pipeline</h2>
        <div className="flex gap-2">
          <Refresh action={() => void query.refetch()} />
          {canEdit && (
            <button
              className="command primary"
              disabled={participants.isPending || vacancies.isPending}
              onClick={create}
            >
              <Plus className="h-4 w-4" /> Add candidate
            </button>
          )}
        </div>
      </div>
      <div className="mb-5 flex flex-wrap gap-3">
        <label className="relative min-w-0 flex-1 sm:max-w-sm">
          <span className="sr-only">Search candidates</span>
          <Search className="absolute left-3 top-3 h-4 w-4 text-muted" />
          <input
            className="field pl-9"
            value={search}
            maxLength={200}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
        <select
          className="field max-w-56"
          aria-label="Stage filter"
          value={status}
          onChange={(event) => setStatus(event.target.value)}
        >
          <option value="">All stages</option>
          {stages.map((item) => (
            <option key={item} value={item}>
              {label(item)}
            </option>
          ))}
        </select>
        <div
          className="flex rounded-md border border-border bg-white p-1"
          aria-label="Pipeline view"
        >
          <button
            className={`icon-button ${mode === "pipeline" ? "bg-primary-soft text-primary" : ""}`}
            title="Pipeline view"
            aria-label="Pipeline view"
            onClick={() => setMode("pipeline")}
          >
            <Columns3 className="h-4 w-4" />
          </button>
          <button
            className={`icon-button ${mode === "table" ? "bg-primary-soft text-primary" : ""}`}
            title="List view"
            aria-label="List view"
            onClick={() => setMode("table")}
          >
            <List className="h-4 w-4" />
          </button>
        </div>
      </div>
      <Feedback pending={query.isPending} error={query.error} />
      {canEdit && selected.length > 0 && (
        <div className="mb-4 flex flex-wrap items-end gap-3 border-y border-border bg-white py-3">
          <label className="min-w-48 flex-1 text-xs text-muted">
            Move {selected.length} selected
            <select
              className="field mt-1"
              aria-label="Bulk destination"
              value={bulkTarget}
              onChange={(event) => setBulkTarget(event.target.value)}
            >
              <option value="">Choose stage</option>
              {bulkTargets.map((target) => (
                <option key={target} value={target}>
                  {label(target)}
                </option>
              ))}
            </select>
          </label>
          <label className="min-w-48 flex-1 text-xs text-muted">
            Reason
            <input
              className="field mt-1"
              value={bulkReason}
              maxLength={5000}
              onChange={(event) => setBulkReason(event.target.value)}
            />
          </label>
          <button
            className="command primary"
            disabled={!bulkTarget || bulkBusy}
            onClick={() => void runBulk()}
          >
            Apply
          </button>
          <button
            className="icon-button"
            aria-label="Clear selection"
            title="Clear selection"
            onClick={() => setSelected([])}
          >
            <X className="h-4 w-4" />
          </button>
          {bulkError && (
            <p className="w-full text-sm text-red-700">{bulkError}</p>
          )}
        </div>
      )}
      {mode === "pipeline" && !status ? (
        <div
          className="matching-board hidden gap-3 overflow-x-auto pb-3 md:grid"
          style={{
            gridTemplateColumns: `repeat(${stages.length}, minmax(240px, 1fr))`,
          }}
        >
          {stages.map((stage) => (
            <StageColumn
              key={stage}
              stage={stage}
              rows={(query.data ?? []).filter((row) => row.status === stage)}
              onOpen={onOpen}
            />
          ))}
        </div>
      ) : (
        <CandidateRows
          rows={query.data ?? []}
          onOpen={onOpen}
          selected={selected}
          onToggle={canEdit ? toggle : undefined}
        />
      )}
      {mode === "pipeline" && !status && (
        <div className="md:hidden">
          <CandidateRows
            rows={query.data ?? []}
            onOpen={onOpen}
            selected={selected}
            onToggle={canEdit ? toggle : undefined}
          />
        </div>
      )}
    </>
  );
}

function StageColumn({
  stage,
  rows,
  onOpen,
}: {
  stage: string;
  rows: Candidate[];
  onOpen: (id: string) => void;
}) {
  return (
    <section className="min-w-0" aria-label={label(stage)}>
      <h3 className="sticky top-0 border-b border-border bg-background px-1 pb-3 text-sm font-semibold">
        {label(stage)} <span className="ml-1 text-muted">{rows.length}</span>
      </h3>
      <div className="space-y-2 pt-3">
        {rows.map((row) => (
          <CandidateCard key={row.id} row={row} onOpen={onOpen} />
        ))}
      </div>
    </section>
  );
}

function CandidateCard({
  row,
  onOpen,
}: {
  row: Candidate;
  onOpen: (id: string) => void;
}) {
  return (
    <button
      className="w-full rounded-md border border-border bg-white p-3 text-left transition hover:border-primary hover:shadow-sm"
      onClick={() => onOpen(row.id)}
    >
      <span className="block break-words text-sm font-semibold">
        {row.participant_name}
      </span>
      <span className="mt-1 block break-words text-xs text-muted">
        {row.vacancy_title} | {row.organization_name}
      </span>
      <span className="mt-3 flex justify-between gap-2 text-xs text-muted">
        <span>{label(row.priority)}</span>
        <span>{row.owner_name ?? "Unassigned"}</span>
      </span>
    </button>
  );
}

function CandidateRows({
  rows,
  onOpen,
  selected = [],
  onToggle,
}: {
  rows: Candidate[];
  onOpen: (id: string) => void;
  selected?: string[];
  onToggle?: (id: string) => void;
}) {
  return (
    <div className="border-t border-border">
      {rows.map((row) => (
        <div key={row.id} className="data-row flex items-start gap-3">
          {onToggle && (
            <input
              type="checkbox"
              className="mt-1 h-4 w-4"
              aria-label={`Select ${row.participant_name}`}
              checked={selected.includes(row.id)}
              onChange={() => onToggle(row.id)}
            />
          )}
          <button
            className="flex min-w-0 flex-1 items-start justify-between gap-4 text-left"
            onClick={() => onOpen(row.id)}
          >
            <span className="min-w-0">
              <span className="block text-sm font-semibold">
                {row.participant_name}
              </span>
              <span className="mt-1 block break-words text-xs text-muted">
                {row.vacancy_title} | {row.organization_name}
              </span>
            </span>
            <span className="shrink-0 text-xs text-muted">
              {label(row.status)}
            </span>
          </button>
        </div>
      ))}
      {!rows.length && (
        <p className="border-b border-border py-10 text-sm text-muted">
          No candidates found
        </p>
      )}
    </div>
  );
}

function MyMatchingWork({ onOpen }: { onOpen: (id: string) => void }) {
  const query = useQuery({
    queryKey: ["matching", "work"],
    queryFn: () =>
      all<Candidate & { due_state: string; recently_assigned: boolean }>(
        "/matching/my-work",
      ),
  });
  return (
    <>
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-xl font-semibold">My Work</h2>
        <Refresh action={() => void query.refetch()} />
      </div>
      <Feedback pending={query.isPending} error={query.error} />
      {[
        "OVERDUE",
        "DUE_TODAY",
        "UPCOMING",
        "HIGH_PRIORITY",
        "RECENTLY_ASSIGNED",
      ].map((bucket) => (
        <section key={bucket} className="mb-7">
          <h3 className="border-b border-border pb-3 text-sm font-semibold">
            {label(bucket)}
          </h3>
          <CandidateRows
            rows={(query.data ?? []).filter((row) =>
              bucket === "HIGH_PRIORITY"
                ? ["HIGH", "URGENT"].includes(row.priority)
                : bucket === "RECENTLY_ASSIGNED"
                  ? row.recently_assigned
                  : row.due_state === bucket,
            )}
            onOpen={onOpen}
          />
        </section>
      ))}
    </>
  );
}

function CandidateDetail({
  id,
  user,
  owners,
  onBack,
  onEditor,
}: {
  id: string;
  user: Me;
  owners: Option[];
  onBack: () => void;
  onEditor: (value: Editor) => void;
}) {
  const query = useQuery({
    queryKey: ["matching", "candidate", id],
    queryFn: () => api<Candidate>(`/candidate-vacancies/${id}`),
  });
  const history = useQuery({
    queryKey: ["matching", "history", id],
    queryFn: () => all<History>(`/candidate-vacancies/${id}/history`),
  });
  const screenings = useQuery({
    queryKey: ["matching", "screenings", id],
    queryFn: () => all<Screening>(`/candidate-vacancies/${id}/screenings`),
  });
  const decisions = useQuery({
    queryKey: ["matching", "decisions", id],
    queryFn: () =>
      all<Decision>(`/candidate-vacancies/${id}/employer-decisions`),
  });
  const row = query.data;
  const canEdit = user.permissions.includes("candidate_pipeline:edit");
  const canInterviewView = user.permissions.includes("interview:view");
  const canInterviewEdit =
    canEdit && user.permissions.includes("interview:edit");
  const interviews = useQuery({
    queryKey: ["matching", "candidate-interviews", id],
    queryFn: () => all<Interview>(`/interviews?candidate_vacancy_id=${id}`),
    enabled: canInterviewView,
  });
  const action = (
    title: string,
    path: string,
    fields: Field[],
    initial: Record<string, unknown> = {},
    extra: Record<string, unknown> = {},
    method?: string,
  ) =>
    row &&
    onEditor({
      title,
      path,
      fields,
      initial,
      extra: { version: row.version, ...extra },
      method,
    });
  return (
    <>
      <button className="command mb-5" onClick={onBack}>
        Back to pipeline
      </button>
      <Feedback pending={query.isPending} error={query.error} />
      {row && (
        <>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm text-muted">{row.participant_code}</p>
              <h2 className="mt-1 text-xl font-semibold">
                {row.participant_name}
              </h2>
              <p className="mt-2 text-sm text-muted">
                {row.vacancy_title} | {row.organization_name}
              </p>
            </div>
            <span className="rounded border border-border bg-white px-2 py-1 text-xs">
              {label(row.status)}
            </span>
          </div>
          {canEdit && (
            <div className="my-6 flex flex-wrap gap-2">
              <button
                className="command"
                onClick={() =>
                  action(
                    "Update candidate",
                    `/candidate-vacancies/${id}`,
                    candidateFields(owners),
                    row as unknown as Record<string, unknown>,
                    { reason: "Recruiter update" },
                    "PATCH",
                  )
                }
              >
                Update
              </button>
              {row.status === "PRE_SCREEN" && (
                <button
                  className="command primary"
                  onClick={() =>
                    action(
                      "Record pre-screen",
                      `/candidate-vacancies/${id}/pre-screen`,
                      screeningFields,
                      {
                        result: "QUALIFIED",
                        participant_interested: true,
                        availability_confirmed: true,
                      },
                    )
                  }
                >
                  Pre-screen
                </button>
              )}
              {row.status === "QUALIFIED" && (
                <button
                  className="command primary"
                  onClick={() =>
                    action(
                      "Submit to employer",
                      `/candidate-vacancies/${id}/submit`,
                      [],
                      {},
                      {},
                    )
                  }
                >
                  Submit
                </button>
              )}
              {canInterviewEdit &&
                ["SUBMITTED", "INTERVIEW", "EMPLOYER_DECISION"].includes(
                  row.status,
                ) && (
                  <button
                    className="command"
                    onClick={() =>
                      onEditor({
                        title: "Schedule interview",
                        path: "/interviews",
                        fields: interviewFields,
                        extra: {
                          candidate_vacancy_id: id,
                          candidate_version: row.version,
                        },
                      })
                    }
                  >
                    <CalendarDays className="h-4 w-4" />
                    Schedule
                  </button>
                )}
              {row.status === "EMPLOYER_DECISION" && (
                <button
                  className="command primary"
                  onClick={() =>
                    action(
                      "Employer decision",
                      `/candidate-vacancies/${id}/employer-decision`,
                      [
                        {
                          key: "decision",
                          label: "Decision",
                          type: "select",
                          required: true,
                          options: ["SELECTED", "REJECTED", "PENDING"].map(
                            (value) => ({ value, label: label(value) }),
                          ),
                        },
                        {
                          key: "reason",
                          label: "Decision reason",
                          type: "textarea",
                          required: true,
                          max: 5000,
                        },
                      ],
                      { decision: "PENDING" },
                    )
                  }
                >
                  <UserRoundCheck className="h-4 w-4" />
                  Decision
                </button>
              )}
              {row.allowed_transitions.map((target) => (
                <button
                  key={target}
                  className="command"
                  onClick={() =>
                    action(
                      label(target),
                      `/candidate-vacancies/${id}/transition`,
                      target.includes("DECLINED") ||
                        [
                          "REJECTED",
                          "WITHDRAWN",
                          "UNREACHABLE",
                          "NOT_INTERESTED",
                          "EMPLOYER_CANCELLED",
                        ].includes(target)
                        ? [
                            {
                              key: "reason",
                              label: "Reason",
                              type: "textarea",
                              required: true,
                              max: 5000,
                            },
                          ]
                        : [],
                      {},
                      { to_status: target },
                    )
                  }
                >
                  {label(target)}
                </button>
              ))}
            </div>
          )}
          <dl className="grid gap-5 border-y border-border py-5 sm:grid-cols-3">
            <div>
              <dt className="text-xs text-muted">Owner</dt>
              <dd className="mt-1 text-sm">{row.owner_name ?? "Unassigned"}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Onboarding</dt>
              <dd className="mt-1 text-sm">{label(row.onboarding_status)}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Next action</dt>
              <dd className="mt-1 text-sm">
                {row.next_action ?? "Not recorded"}
              </dd>
            </div>
          </dl>
          <section className="mt-8">
            <h3 className="mb-3 text-base font-semibold">Recorded evidence</h3>
            <Feedback
              pending={screenings.isPending || decisions.isPending}
              error={screenings.error ?? decisions.error}
            />
            {screenings.data?.map((item) => (
              <div key={item.id} className="data-row">
                <p className="text-sm font-semibold">
                  Pre-screen: {label(item.result)}
                </p>
                <p className="mt-1 text-xs text-muted">
                  Interest{" "}
                  {item.participant_interested ? "confirmed" : "not confirmed"}{" "}
                  | Availability{" "}
                  {item.availability_confirmed ? "confirmed" : "not confirmed"}{" "}
                  | {time(item.created_at)}
                </p>
                {item.notes && <p className="mt-2 text-sm">{item.notes}</p>}
              </div>
            ))}
            {decisions.data?.map((item) => (
              <div key={item.id} className="data-row">
                <p className="text-sm font-semibold">
                  Employer decision: {label(item.decision)}
                </p>
                <p className="mt-1 text-sm">{item.reason}</p>
                <p className="mt-1 text-xs text-muted">
                  {time(item.created_at)}
                </p>
              </div>
            ))}
            {interviews.data?.map((item) => (
              <div key={item.id} className="data-row">
                <p className="text-sm font-semibold">
                  Interview: {label(item.status)}
                </p>
                <p className="mt-1 text-xs text-muted">
                  {time(item.scheduled_at)} | {label(item.format)} |{" "}
                  {item.location_or_link}
                </p>
                {item.outcome && (
                  <p className="mt-1 text-sm">Outcome: {label(item.outcome)}</p>
                )}
                <InterviewHistoryRows id={item.id} />
              </div>
            ))}
            {!screenings.isPending &&
              !decisions.isPending &&
              !screenings.data?.length &&
              !decisions.data?.length &&
              !interviews.data?.length && (
                <p className="border-b border-border py-5 text-sm text-muted">
                  No evidence recorded yet
                </p>
              )}
          </section>
          <section className="mt-8">
            <h3 className="mb-3 text-base font-semibold">Status history</h3>
            <Feedback pending={history.isPending} error={history.error} />
            {history.data?.map((item) => (
              <div
                key={item.id}
                className="data-row flex justify-between gap-4"
              >
                <span className="text-sm">
                  {label(item.to_status)}
                  {item.reason ? ` | ${item.reason}` : ""}
                </span>
                <span className="shrink-0 text-xs text-muted">
                  {time(item.occurred_at)}
                </span>
              </div>
            ))}
          </section>
        </>
      )}
    </>
  );
}

function InterviewHistoryRows({ id }: { id: string }) {
  const query = useQuery({
    queryKey: ["matching", "interview-history", id],
    queryFn: () => all<InterviewHistory>(`/interviews/${id}/history`),
  });
  if (query.isPending)
    return <p className="mt-2 text-xs text-muted">Loading history...</p>;
  if (query.error)
    return <p className="mt-2 text-xs text-red-700">{query.error.message}</p>;
  return (
    <ol className="mt-2 border-l border-border pl-3">
      {query.data?.map((item) => (
        <li key={item.id} className="py-1 text-xs text-muted">
          {label(item.to_status)} | {time(item.occurred_at)}
          {item.reason ? ` | ${item.reason}` : ""}
        </li>
      ))}
    </ol>
  );
}

function InterviewDay({
  user,
  onCandidate,
  onEditor,
}: {
  user: Me;
  onCandidate: (id: string) => void;
  onEditor: (value: Editor) => void;
}) {
  const [day, setDay] = useState(new Date().toISOString().slice(0, 10));
  const query = useQuery({
    queryKey: ["matching", "interviews", day],
    queryFn: () => all<Interview>(`/interviews?day=${day}`),
  });
  const act = (
    row: Interview,
    action: string,
    fields: Field[],
    extra: Record<string, unknown> = {},
  ) =>
    onEditor({
      title: label(action),
      path: `/interviews/${row.id}/${action}`,
      fields,
      extra: { version: row.version, ...extra },
    });
  return (
    <>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">Interview Day</h2>
        <div className="flex gap-2">
          <input
            className="field"
            aria-label="Interview date"
            type="date"
            value={day}
            onChange={(event) => setDay(event.target.value)}
          />
          <Refresh action={() => void query.refetch()} />
        </div>
      </div>
      <Feedback pending={query.isPending} error={query.error} />
      <div className="border-t border-border">
        {query.data?.map((row) => (
          <article key={row.id} className="data-row">
            <button
              className="w-full text-left"
              onClick={() => onCandidate(row.candidate_vacancy_id)}
            >
              <span className="text-sm font-semibold">
                {time(row.scheduled_at)} | {row.participant_name}
              </span>
              <span className="mt-1 block text-xs text-muted">
                {row.vacancy_title} | {label(row.format)} |{" "}
                {row.location_or_link} | {label(row.status)}
              </span>
            </button>
            {user.permissions.includes("interview:edit") && (
              <div className="mt-3 flex flex-wrap gap-2">
                {["SCHEDULED", "RESCHEDULED"].includes(row.status) && (
                  <>
                    <button
                      className="command"
                      onClick={() =>
                        act(row, "attend", [
                          {
                            key: "reason",
                            label: "Attendance note",
                            type: "textarea",
                            required: true,
                          },
                        ])
                      }
                    >
                      <Check className="h-4 w-4" />
                      Attended
                    </button>
                    <button
                      className="command"
                      onClick={() =>
                        act(row, "no-show", [
                          {
                            key: "reason",
                            label: "Reason",
                            type: "textarea",
                            required: true,
                          },
                        ])
                      }
                    >
                      No-show
                    </button>
                    <button
                      className="command"
                      onClick={() =>
                        act(row, "reschedule", [
                          {
                            key: "scheduled_at",
                            label: "New date and time (Ghana time)",
                            type: "datetime-local",
                            required: true,
                          },
                          {
                            key: "reason",
                            label: "Reason",
                            type: "textarea",
                            required: true,
                          },
                        ])
                      }
                    >
                      Reschedule
                    </button>
                    <button
                      className="command"
                      onClick={() =>
                        act(row, "cancel", [
                          {
                            key: "reason",
                            label: "Reason",
                            type: "textarea",
                            required: true,
                          },
                        ])
                      }
                    >
                      Cancel
                    </button>
                  </>
                )}
                {row.status === "ATTENDED" && (
                  <button
                    className="command primary"
                    onClick={() =>
                      act(row, "outcome", [
                        {
                          key: "outcome",
                          label: "Outcome",
                          type: "select",
                          required: true,
                          options: [
                            "PASSED",
                            "REJECTED",
                            "PENDING_EMPLOYER_DECISION",
                            "NOT_APPLICABLE",
                          ].map((value) => ({ value, label: label(value) })),
                        },
                        {
                          key: "reason",
                          label: "Outcome note",
                          type: "textarea",
                          required: true,
                        },
                      ])
                    }
                  >
                    Record outcome
                  </button>
                )}
              </div>
            )}
          </article>
        ))}
      </div>
      {query.data?.length === 0 && (
        <div className="flex min-h-44 flex-col items-center justify-center gap-3 border-b border-border text-muted">
          <CalendarDays className="h-6 w-6" />
          <p className="text-sm">No interviews scheduled</p>
        </div>
      )}
    </>
  );
}
