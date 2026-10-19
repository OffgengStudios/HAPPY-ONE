"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  Plus,
  RefreshCw,
} from "lucide-react";
import { Children, useState } from "react";
import { all, api, Me } from "@/lib/api";
import { label } from "@/lib/matching";
import { DataQualityIssue, FollowUp, MerlDashboard, Outcome } from "@/lib/merl";
import { Placement } from "@/lib/placement";
import { DemandForm, Editor } from "./demand-form";

const options = (values: string[]) =>
  values.map((value) => ({ value, label: label(value) }));

export function MerlWorkspace({ view, user }: { view: string; user: Me }) {
  const client = useQueryClient();
  const [editor, setEditor] = useState<Editor | null>(null);
  const section = view === "work" ? "follow-ups" : view;
  const followUps = useQuery({
    queryKey: ["merl", "follow-ups"],
    queryFn: () => all<FollowUp>("/follow-ups"),
  });
  const outcomes = useQuery({
    queryKey: ["merl", "outcomes"],
    queryFn: () => all<Outcome>("/outcomes"),
  });
  const issues = useQuery({
    queryKey: ["merl", "data-quality"],
    queryFn: () => all<DataQualityIssue>("/data-quality/issues"),
  });
  const dashboard = useQuery({
    queryKey: ["merl", "dashboard"],
    queryFn: () => api<MerlDashboard>("/merl/dashboard"),
  });
  const placements = useQuery({
    queryKey: ["placements"],
    queryFn: () => all<Placement>("/placements"),
  });
  const placementOptions = (placements.data ?? [])
    .filter((row) => Boolean(row.actual_start_date))
    .map((row) => ({
      value: row.id,
      label: `${row.participant_name} | ${row.organization_name}`,
    }));
  const completedOptions = (followUps.data ?? [])
    .filter(
      (row) =>
        row.status === "COMPLETED" &&
        !(outcomes.data ?? []).some((item) => item.follow_up_id === row.id),
    )
    .map((row) => ({
      value: row.id,
      label: `${row.participant_name} | ${row.scheduled_for}`,
    }));
  const refresh = async () => {
    await client.invalidateQueries({ queryKey: ["merl"] });
    await client.invalidateQueries({ queryKey: ["placements"] });
  };
  const openFollowUp = () =>
    setEditor({
      title: "Schedule follow-up",
      path: "/follow-ups",
      fields: [
        {
          key: "placement_id",
          label: "Placement",
          type: "select",
          required: true,
          options: placementOptions,
        },
        {
          key: "follow_up_type",
          label: "Follow-up type",
          type: "select",
          required: true,
          options: options([
            "EMPLOYMENT_VERIFICATION",
            "RETENTION_CHECK",
            "SUPPORT_CHECK",
          ]),
        },
        {
          key: "scheduled_for",
          label: "Scheduled date",
          type: "date",
          required: true,
        },
      ],
    });
  const openOutcome = () =>
    setEditor({
      title: "Record verified outcome",
      path: "/outcomes",
      fields: [
        {
          key: "placement_id",
          label: "Placement",
          type: "select",
          required: true,
          options: placementOptions,
        },
        {
          key: "follow_up_id",
          label: "Completed follow-up",
          type: "select",
          options: completedOptions,
        },
        {
          key: "as_of_date",
          label: "Observation date",
          type: "date",
          required: true,
        },
        {
          key: "currently_working",
          label: "Currently working",
          type: "checkbox",
        },
        { key: "current_employer", label: "Current employer", max: 200 },
        { key: "current_role", label: "Current role", max: 200 },
        {
          key: "job_satisfaction",
          label: "Job satisfaction (1-5)",
          type: "number",
          min: 1,
          max: 5,
        },
        {
          key: "progress_text",
          label: "Progress",
          type: "textarea",
          max: 5000,
        },
        {
          key: "support_needed_text",
          label: "Support needed",
          type: "textarea",
          max: 5000,
        },
        {
          key: "impact_story_potential",
          label: "Potential impact story",
          type: "checkbox",
        },
      ],
    });
  const complete = (row: FollowUp) =>
    setEditor({
      title: "Complete follow-up",
      path: `/follow-ups/${row.id}/complete`,
      fields: [
        {
          key: "contact_result",
          label: "Contact result",
          type: "select",
          required: true,
          options: options([
            "REACHED",
            "NOT_REACHED",
            "DECLINED",
            "RESCHEDULED",
          ]),
        },
        {
          key: "notes",
          label: "Verification notes",
          type: "textarea",
          required: true,
          max: 5000,
        },
      ],
      extra: { version: row.version },
    });
  const resolve = (row: DataQualityIssue) =>
    setEditor({
      title: "Resolve data-quality issue",
      path: `/data-quality/issues/${row.id}/resolve`,
      fields: [
        {
          key: "resolution",
          label: "Resolution",
          type: "select",
          required: true,
          options: options(["RESOLVED", "DISMISSED"]),
        },
        {
          key: "notes",
          label: "Resolution notes",
          type: "textarea",
          required: true,
          max: 5000,
        },
      ],
      extra: { version: row.version },
    });
  const pending =
    followUps.isPending ||
    outcomes.isPending ||
    issues.isPending ||
    dashboard.isPending;
  const error =
    followUps.error || outcomes.error || issues.error || dashboard.error;
  return (
    <div className="min-w-0">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase text-primary">
            M&amp;E / MERL
          </p>
          <h2 className="mt-1 text-xl font-semibold">
            {section === "dashboard" ? "Outcome Dashboard" : label(section)}
          </h2>
        </div>
        <div className="flex gap-2">
          <button
            className="icon-button"
            title="Refresh"
            aria-label="Refresh"
            onClick={() => void refresh()}
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          {section === "follow-ups" &&
            user.permissions.includes("follow_up:edit") && (
              <button
                className="command primary"
                disabled={placements.isPending || !placementOptions.length}
                onClick={openFollowUp}
              >
                <Plus className="h-4 w-4" />
                Schedule
              </button>
            )}
          {section === "outcomes" &&
            user.permissions.includes("outcome:edit") && (
              <button
                className="command primary"
                disabled={placements.isPending || !placementOptions.length}
                onClick={openOutcome}
              >
                <Plus className="h-4 w-4" />
                Record outcome
              </button>
            )}
        </div>
      </div>
      {pending && (
        <p role="status" className="py-6 text-sm text-muted">
          Loading M&amp;E records...
        </p>
      )}
      {error && (
        <p role="alert" className="py-4 text-sm text-red-700">
          {error.message}
        </p>
      )}
      {section === "dashboard" && dashboard.data && (
        <Dashboard data={dashboard.data} />
      )}
      {section === "follow-ups" && (
        <Rows empty="No follow-ups scheduled">
          {(followUps.data ?? []).map((row) => (
            <button
              key={row.id}
              className="data-row flex w-full items-center justify-between gap-4 text-left"
              onClick={() =>
                !["COMPLETED", "CANCELLED"].includes(row.status) &&
                complete(row)
              }
            >
              <span>
                <strong className="block text-sm">
                  {row.participant_name}
                </strong>
                <span className="mt-1 block text-xs text-muted">
                  {label(row.follow_up_type)} | {row.scheduled_for}
                </span>
              </span>
              <span className="text-xs text-muted">{label(row.status)}</span>
            </button>
          ))}
        </Rows>
      )}
      {section === "outcomes" && (
        <Rows empty="No outcomes recorded">
          {(outcomes.data ?? []).map((row) => (
            <div
              key={row.id}
              className="data-row flex items-start justify-between gap-4"
            >
              <span>
                <strong className="block text-sm">
                  {row.participant_name}
                </strong>
                <span className="mt-1 block text-xs text-muted">
                  Observed {row.as_of_date}
                  {row.current_role ? ` | ${row.current_role}` : ""}
                </span>
              </span>
              <span className="text-right text-xs text-muted">
                {row.currently_working ? "Working" : "Not working"}
                {row.impact_story_potential && (
                  <span className="mt-1 block text-primary">Impact story</span>
                )}
              </span>
            </div>
          ))}
        </Rows>
      )}
      {section === "data-quality" && (
        <Rows empty="No data-quality issues">
          {(issues.data ?? []).map((row) => (
            <button
              key={row.id}
              className="data-row flex w-full items-start justify-between gap-4 text-left"
              onClick={() =>
                !["RESOLVED", "DISMISSED"].includes(row.status) &&
                user.permissions.includes("data_quality:edit") &&
                resolve(row)
              }
            >
              <span>
                <strong className="block text-sm">
                  {label(row.issue_type)}
                </strong>
                <span className="mt-1 block text-xs text-muted">
                  {row.description}
                </span>
              </span>
              <span className="text-right text-xs text-muted">
                {label(row.severity)}
                <span className="mt-1 block">{label(row.status)}</span>
              </span>
            </button>
          ))}
        </Rows>
      )}
      {editor && (
        <DemandForm
          editor={editor}
          onClose={() => setEditor(null)}
          onSaved={async () => {
            setEditor(null);
            await refresh();
          }}
          onReview={async () => {
            setEditor(null);
            await refresh();
          }}
        />
      )}
    </div>
  );
}

function Rows({
  children,
  empty,
}: {
  children: React.ReactNode;
  empty: string;
}) {
  return (
    <div className="border-t border-border">
      {Children.count(children) ? (
        children
      ) : (
        <p className="border-b border-border py-8 text-sm text-muted">
          {empty}
        </p>
      )}
    </div>
  );
}

function Dashboard({ data }: { data: MerlDashboard }) {
  const measures = [
    ["Scheduled", data.scheduled, CalendarClock],
    ["Due", data.due, CalendarClock],
    ["Overdue", data.overdue, AlertTriangle],
    ["Completed", data.completed, CheckCircle2],
    ["Verified working", data.latest_verified_working, CheckCircle2],
    ["Impact stories", data.impact_story_candidates, CheckCircle2],
    ["Open data quality", data.open_data_quality, AlertTriangle],
  ] as const;
  return (
    <dl className="grid border-l border-t border-border sm:grid-cols-2 lg:grid-cols-4">
      {measures.map(([name, value, Icon]) => (
        <div key={name} className="border-b border-r border-border p-5">
          <dt className="flex items-center gap-2 text-xs text-muted">
            <Icon className="h-4 w-4" />
            {name}
          </dt>
          <dd className="mt-3 text-2xl font-semibold">{value}</dd>
        </div>
      ))}
    </dl>
  );
}
