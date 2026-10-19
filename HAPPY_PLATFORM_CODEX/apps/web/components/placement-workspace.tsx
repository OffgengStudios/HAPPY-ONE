"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Banknote, CalendarCheck, Plus, RefreshCw } from "lucide-react";
import { useState } from "react";
import { all, Me, time } from "@/lib/api";
import { Field } from "@/lib/demand";
import { Candidate, label } from "@/lib/matching";
import { Placement, placementFields } from "@/lib/placement";
import { DemandForm, Editor } from "./demand-form";

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
        Loading placements...
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

export function PlacementWorkspace({
  view,
  user,
  initialIdentifier = null,
}: {
  view: string;
  user: Me;
  initialIdentifier?: string | null;
}) {
  const client = useQueryClient();
  const [selected, setSelected] = useState<string | null>(initialIdentifier);
  const [editor, setEditor] = useState<Editor | null>(null);
  const placements = useQuery({
    queryKey: ["placements"],
    queryFn: () => all<Placement>("/placements"),
  });
  const selectedCandidates = useQuery({
    queryKey: ["placements", "selected-candidates"],
    queryFn: () => all<Candidate>("/candidate-vacancies?status=SELECTED"),
    enabled: user.permissions.includes("placement:edit"),
  });
  const rows = placements.data ?? [];
  const current = rows.find((row) => row.id === selected) ?? null;
  const canEdit = user.permissions.includes("placement:edit");
  const canConfirm = user.permissions.includes("placement:confirm");
  const open = (
    title: string,
    path: string,
    fields: Field[],
    extra: Record<string, unknown>,
    initial: Record<string, unknown> = {},
  ) => setEditor({ title, path, fields, extra, initial });
  const create = () =>
    setEditor({
      title: "Create placement",
      path: "/placements",
      fields: [
        {
          key: "candidate_vacancy_id",
          label: "Selected candidate",
          type: "select",
          required: true,
          options: (selectedCandidates.data ?? []).map((row) => ({
            value: row.id,
            label: `${row.participant_name} | ${row.vacancy_title}`,
          })),
        },
        ...placementFields,
      ],
      initial: { payroll_frequency: "MONTHLY", salary_frequency: "MONTHLY" },
      extra: {},
    });
  return (
    <div className="min-w-0">
      {current ? (
        <>
          <button className="command mb-5" onClick={() => setSelected(null)}>
            Back to placements
          </button>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm text-muted">{current.placement_code}</p>
              <h2 className="mt-1 text-xl font-semibold">
                {current.participant_name}
              </h2>
              <p className="mt-2 text-sm text-muted">
                {current.vacancy_title} | {current.organization_name}
              </p>
            </div>
            <span className="rounded border border-border bg-white px-2 py-1 text-xs">
              {label(current.status)}
            </span>
          </div>
          <div className="my-6 flex flex-wrap gap-2">
            {canEdit && current.status === "START_PENDING" && (
              <>
                <button
                  className="command primary"
                  onClick={() =>
                    open(
                      "Confirm actual start",
                      `/placements/${current.id}/confirm-start`,
                      [
                        {
                          key: "actual_start_date",
                          label: "Actual start date",
                          type: "date",
                          required: true,
                        },
                        {
                          key: "manual_first_income_date",
                          label: "Manual first-income date",
                          type: "date",
                        },
                        {
                          key: "exception_reason",
                          label: "Exception reason",
                          type: "textarea",
                          max: 5000,
                        },
                        {
                          key: "notes",
                          label: "Verification note",
                          type: "textarea",
                          max: 5000,
                        },
                      ],
                      { version: current.version },
                    )
                  }
                >
                  Confirm start
                </button>
                <button
                  className="command"
                  onClick={() =>
                    open(
                      "Close pending start",
                      `/placements/${current.id}/start-outcome`,
                      [
                        {
                          key: "outcome",
                          label: "Outcome",
                          type: "select",
                          required: true,
                          options: ["FAILED_TO_START", "CANCELLED"].map(
                            (value) => ({ value, label: label(value) }),
                          ),
                        },
                        {
                          key: "effective_date",
                          label: "Effective date",
                          type: "date",
                          required: true,
                        },
                        {
                          key: "reason",
                          label: "Reason",
                          type: "textarea",
                          required: true,
                          max: 5000,
                        },
                      ],
                      { version: current.version },
                    )
                  }
                >
                  Close start
                </button>
              </>
            )}
            {canConfirm && current.status === "AWAITING_FIRST_INCOME" && (
              <button
                className="command primary"
                onClick={() =>
                  open(
                    "Confirm first income",
                    `/placements/${current.id}/first-income/confirm`,
                    [
                      {
                        key: "actual_income_received_date",
                        label: "Income received date",
                        type: "date",
                        required: true,
                      },
                      {
                        key: "amount_received",
                        label: "Amount received",
                        type: "number",
                        min: 0,
                      },
                      {
                        key: "notes",
                        label: "Verification evidence",
                        type: "textarea",
                        required: true,
                        max: 5000,
                      },
                    ],
                    { version: current.first_income.version },
                  )
                }
              >
                <Banknote className="h-4 w-4" />
                Confirm income
              </button>
            )}
            {user.permissions.includes("first_income:edit") &&
              current.status === "AWAITING_FIRST_INCOME" && (
                <>
                  <button
                    className="command"
                    onClick={() =>
                      open(
                        "Record payment delay",
                        `/placements/${current.id}/first-income/delay`,
                        [
                          {
                            key: "verification_due_date",
                            label: "Revised due date",
                            type: "date",
                            required: true,
                          },
                          {
                            key: "reason",
                            label: "Delay reason",
                            type: "textarea",
                            required: true,
                            max: 5000,
                          },
                        ],
                        { version: current.first_income.version },
                      )
                    }
                  >
                    Payment delayed
                  </button>
                  <button
                    className="command"
                    onClick={() =>
                      open(
                        "Resolve schedule exception",
                        `/placements/${current.id}/first-income/exception`,
                        [
                          {
                            key: "verification_due_date",
                            label: "Manual due date",
                            type: "date",
                            required: true,
                          },
                          {
                            key: "reason",
                            label: "Exception reason",
                            type: "textarea",
                            required: true,
                            max: 5000,
                          },
                        ],
                        { version: current.first_income.version },
                      )
                    }
                  >
                    Schedule exception
                  </button>
                </>
              )}
            {canEdit &&
              ["AWAITING_FIRST_INCOME", "CONFIRMED"].includes(
                current.status,
              ) && (
                <button
                  className="command"
                  onClick={() =>
                    open(
                      "Record employment end",
                      `/placements/${current.id}/employment-end`,
                      [
                        {
                          key: "employment_end_date",
                          label: "Employment end date",
                          type: "date",
                          required: true,
                        },
                        {
                          key: "reason",
                          label: "Reason",
                          type: "textarea",
                          required: true,
                          max: 5000,
                        },
                      ],
                      { version: current.version },
                    )
                  }
                >
                  Employment ended
                </button>
              )}
          </div>
          <dl className="grid gap-5 border-y border-border py-5 sm:grid-cols-3">
            <div>
              <dt className="text-xs text-muted">Actual start</dt>
              <dd className="mt-1 text-sm">
                {current.actual_start_date ?? "Pending"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted">First income due</dt>
              <dd className="mt-1 text-sm">
                {current.expected_first_income_date ?? "Exception review"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Verification</dt>
              <dd className="mt-1 text-sm">
                {label(current.first_income.status)}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Confirmed</dt>
              <dd className="mt-1 text-sm">{time(current.confirmed_at)}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Currently working</dt>
              <dd className="mt-1 text-sm">
                {current.currently_working === null
                  ? "Not recorded"
                  : current.currently_working
                    ? "Yes"
                    : "No"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Owner</dt>
              <dd className="mt-1 text-sm">
                {current.owner_name ?? "Unassigned"}
              </dd>
            </div>
          </dl>
        </>
      ) : (
        <>
          <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-xl font-semibold">
              {view === "first-income" ? "First Income" : "Placements"}
            </h2>
            <div className="flex gap-2">
              <button
                className="icon-button"
                title="Refresh"
                aria-label="Refresh"
                onClick={() => void placements.refetch()}
              >
                <RefreshCw className="h-4 w-4" />
              </button>
              {canEdit && view !== "first-income" && (
                <button
                  className="command primary"
                  disabled={
                    selectedCandidates.isPending ||
                    !selectedCandidates.data?.length
                  }
                  onClick={create}
                >
                  <Plus className="h-4 w-4" />
                  New placement
                </button>
              )}
            </div>
          </div>
          <Feedback pending={placements.isPending} error={placements.error} />
          {(view === "first-income"
            ? ["OVERDUE", "DUE", "UPCOMING", "PAYMENT_DELAYED", "EXCEPTION"]
            : [""]
          ).map((bucket) => {
            const filtered =
              view === "first-income"
                ? rows.filter(
                    (row) =>
                      row.status === "AWAITING_FIRST_INCOME" &&
                      row.first_income.status === bucket,
                  )
                : rows;
            return (
              <section key={bucket || "all"} className="mb-7">
                {bucket && (
                  <h3 className="border-b border-border pb-3 text-sm font-semibold">
                    {label(bucket)}
                  </h3>
                )}
                <div className="border-t border-border">
                  {filtered.map((row) => (
                    <button
                      key={row.id}
                      className="data-row flex w-full items-start justify-between gap-4 text-left"
                      onClick={() => setSelected(row.id)}
                    >
                      <span>
                        <span className="block text-sm font-semibold">
                          {row.participant_name}
                        </span>
                        <span className="mt-1 block text-xs text-muted">
                          {row.vacancy_title} | {row.organization_name}
                        </span>
                      </span>
                      <span className="shrink-0 text-xs text-muted">
                        {label(
                          view === "first-income"
                            ? row.first_income.status
                            : row.status,
                        )}
                      </span>
                    </button>
                  ))}
                  {!filtered.length && (
                    <p className="border-b border-border py-8 text-sm text-muted">
                      No records
                    </p>
                  )}
                </div>
              </section>
            );
          })}
          {!rows.length && !placements.isPending && (
            <div className="flex min-h-40 flex-col items-center justify-center gap-3 text-muted">
              <CalendarCheck className="h-6 w-6" />
              <p className="text-sm">No placements recorded</p>
            </div>
          )}
        </>
      )}
      {editor && (
        <DemandForm
          editor={editor}
          onClose={() => setEditor(null)}
          onSaved={async (row) => {
            const saved = row as Placement;
            client.setQueryData<Placement[]>(["placements"], (currentRows) => {
              if (!currentRows) return [saved];
              const exists = currentRows.some((item) => item.id === saved.id);
              return exists
                ? currentRows.map((item) =>
                    item.id === saved.id ? saved : item,
                  )
                : [saved, ...currentRows];
            });
            setEditor(null);
            await client.invalidateQueries({ queryKey: ["placements"] });
            if (saved.id) setSelected(String(saved.id));
          }}
          onReview={async () => {
            setEditor(null);
            await client.invalidateQueries({ queryKey: ["placements"] });
          }}
        />
      )}
    </div>
  );
}
