"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { all, Me } from "@/lib/api";
import { Field } from "@/lib/demand";
import { Participant, SupplyItem } from "@/lib/supply";
import { Editor } from "./demand-form";
import { placementDetailFields } from "@/lib/placement";

const modules = [
  "Good Agronomic and Production Practices",
  "Animal Husbandry & Health",
  "Post-Harvest Management and Value Addition",
  "Business/Marketing",
  "Financial Literacy",
  "Soft Skills",
  "Training/Skill Development Modules",
  "IT Skills",
];
const choices = (key: string, label: string, values: string[]): Field => ({
  key,
  label,
  type: "select",
  options: values.map((value) => ({
    value,
    label: value.replaceAll("_", " "),
  })),
});
export const outcomeFields: Field[] = [
  {
    key: "employment_start_date",
    label: "Employment Start Date",
    type: "date",
    required: true,
  },
  {
    key: "as_of_date",
    label: "Observation Date",
    type: "date",
    required: true,
  },
  { key: "currently_working", label: "Currently working", type: "checkbox" },
  choices("employment_type", "Employment Type", ["WAGE", "SELF"]),
  choices("employment_category", "Employment Category", [
    "NEW",
    "IMPROVED",
    "ADDITIONAL",
  ]),
  { key: "job_type", label: "Job Type", max: 60 },
  { key: "current_employer", label: "Employer / business name", max: 200 },
  { key: "current_role", label: "Job Role", max: 200 },
  {
    key: "verification_notes",
    label: "Verification evidence and notes",
    type: "textarea",
    required: true,
    max: 5000,
  },
];

const agricultureFields: Field[] = [
  {
    key: "include_agriculture",
    label: "Record agriculture outcomes",
    type: "checkbox",
    uiOnly: true,
  },
  ...[
    { key: "agriculture.sector", label: "Agriculture Sector", max: 60 },
    {
      key: "agriculture.farm_management_services",
      label: "Farm Management Services",
      max: 200,
    },
    ...[
      ["farm_size_acres", "Farm Size (Acres)"],
      ["seed_kg", "Seed (Kg)"],
      ["fertilizer_kg", "Fertilizer (Kg)"],
      ["crop_protection_litre", "Crop Protection (Litre)"],
      ["inoculant_g", "Inoculant (g)"],
      ["volumes_harvested", "Volumes Harvested"],
    ].map(
      ([key, label]) =>
        ({
          key: "agriculture." + key,
          label,
          type: "number",
          min: 0,
          step: "0.01",
        }) as Field,
    ),
    { key: "agriculture.harvest_unit", label: "Harvest unit", max: 60 },
  ].map((field) => ({
    ...field,
    showWhen: { key: "include_agriculture", value: "true" },
  })),
];

function Detail({ values }: { values: Record<string, unknown> }) {
  return (
    <dl className="grid gap-4 py-4 sm:grid-cols-2 lg:grid-cols-3">
      {Object.entries(values).map(([key, value]) => (
        <div key={key} className="min-w-0">
          <dt className="text-xs text-muted">{key}</dt>
          <dd className="break-words text-sm">
            {value === null || value === undefined
              ? "Not recorded"
              : typeof value === "boolean"
                ? value
                  ? "Yes"
                  : "No"
                : String(value)}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function ParticipantLifecycle({
  stage,
  row,
  user,
  onEditor,
}: {
  stage: string;
  row: Participant;
  user: Me;
  onEditor: (editor: Editor) => void;
}) {
  const capacity = stage === "Capacity Building";
  const [trainingId, setTrainingId] = useState("");
  const can = (permission: string) => user.permissions.includes(permission);
  const trainings = useQuery({
    queryKey: ["supply", "capacity", row.id],
    queryFn: () => all<SupplyItem>(`/participants/${row.id}/capacity-building`),
    enabled: capacity && can("training:view"),
  });
  const placements = useQuery({
    queryKey: ["supply", "placements", row.id],
    queryFn: () => all<SupplyItem>(`/participants/${row.id}/placements`),
    enabled: !capacity && can("placement:view"),
  });
  const outcomes = useQuery({
    queryKey: ["supply", "outcomes", row.id],
    queryFn: () =>
      all<SupplyItem>(`/participants/${row.id}/employment-outcomes`),
    enabled: !capacity && can("outcome:view"),
  });
  const available = useQuery({
    queryKey: ["supply", "available-trainings"],
    queryFn: () => all<SupplyItem>("/trainings"),
    enabled: capacity && can("training:edit"),
  });
  function recordOutcome() {
    onEditor({
      title: "Record verified employment outcome",
      path: `/participants/${row.id}/employment-outcomes`,
      fields: [
        ...outcomeFields,
        ...agricultureFields,
        ...(can("participant_sensitive:edit")
          ? [
              choices("income_status", "Income recording status", [
                "KNOWN",
                "UNKNOWN",
                "NOT_RECORDED",
                "NOT_APPLICABLE",
              ]),
              {
                key: "current_income_amount",
                label: "Income (GHS)",
                type: "number",
                min: 0,
                step: "0.01",
              } as Field,
              choices("income_frequency", "Income frequency", [
                "DAILY",
                "WEEKLY",
                "BIWEEKLY",
                "MONTHLY",
                "OTHER",
              ]),
            ]
          : []),
      ],
      initial: { currently_working: true },
    });
  }
  return (
    <section className="space-y-5">
      <h3 className="text-base font-semibold">{stage}</h3>
      <p className="text-sm text-muted">
        {capacity
          ? "Each enrolment has its own training dates, attendance, modules and certificate. Age is calculated at training start."
          : "Placement records and dated employment outcomes preserve the onboarding baseline. Entered income does not confirm a placement."}
      </p>
      {capacity && !can("training:view") && (
        <p>Training access is required to view enrolments.</p>
      )}
      {capacity && can("training:edit") && (
        <div className="flex flex-wrap gap-3">
          <label className="field-label">
            Training event
            <select
              className="field"
              value={trainingId}
              onChange={(event) => setTrainingId(event.target.value)}
            >
              <option value="">Select a training event</option>
              {(available.data ?? [])
                .filter(
                  (training) =>
                    !(trainings.data ?? []).some(
                      (enrolment) => enrolment.training_id === training.id,
                    ),
                )
                .map((training) => (
                  <option key={training.id} value={training.id}>
                    {String(training.title)}
                  </option>
                ))}
            </select>
          </label>
          <button
            disabled={!trainingId}
            className="command"
            onClick={() =>
              onEditor({
                title: "Enrol participant in training",
                path: `/trainings/${trainingId}/participants`,
                fields: [],
                extra: { participant_ids: [row.id] },
              })
            }
          >
            Enrol in training
          </button>
          <button
            className="command"
            onClick={() =>
              window.dispatchEvent(
                new CustomEvent("happy:navigate", {
                  detail: { view: "training" },
                }),
              )
            }
          >
            Manage training events
          </button>
        </div>
      )}
      {[trainings, placements, outcomes]
        .filter((query) => !!query.error)
        .map((query, index) => (
          <p key={index} role="alert">
            {query.error instanceof Error
              ? query.error.message
              : "Unable to load records."}
          </p>
        ))}
      {capacity && trainings.isFetching && (
        <p role="status">Loading enrolments…</p>
      )}
      {capacity && trainings.data?.length === 0 && (
        <p>No training enrolments recorded.</p>
      )}
      {capacity &&
        trainings.data?.map((item) => {
          const training = item.training as SupplyItem;
          return (
            <article
              key={item.id}
              className="rounded-lg border border-border p-4"
            >
              <h4 className="font-semibold">{String(training.title)}</h4>
              <Detail
                values={{
                  "Start Date": training.start_date,
                  "End Date": training.end_date,
                  "Training Location":
                    training.location_text ?? training.location_community,
                  "Age at Training Start": item.age_at_training_start,
                  "Projected age": item.age_projected,
                  "Agriculture Sector": training.agriculture_sector,
                  "Trainer Type": training.trainer_type,
                  "Training Partner": training.partner_name,
                  Attendance: item.attendance_status,
                  "Completion Status": item.completion_status,
                  "Certificate issued": item.certificate_issued,
                  "Received modules": (
                    (item.received_modules as string[]) ?? []
                  ).join(", "),
                  "Completed modules": (
                    (item.completed_modules as string[]) ?? []
                  ).join(", "),
                }}
              />
              {can("training:edit") && (
                <button
                  className="command"
                  onClick={() =>
                    onEditor({
                      title: "Update individual learning",
                      path: `/training-attendance/${item.id}`,
                      method: "PATCH",
                      initial: item,
                      extra: { version: item.version },
                      fields: [
                        {
                          ...choices("attendance_status", "Attendance", [
                            "PRESENT",
                            "ABSENT",
                            "LATE",
                            "EXCUSED",
                          ]),
                          required: true,
                        },
                        {
                          ...choices("completion_status", "Completion Status", [
                            "NOT_STARTED",
                            "IN_PROGRESS",
                            "COMPLETED",
                            "NOT_COMPLETED",
                          ]),
                          required: true,
                        },
                        {
                          key: "received_modules",
                          label: "Modules received (one per line)",
                          type: "list",
                        },
                        {
                          key: "completed_modules",
                          label: "Modules completed (one per line)",
                          type: "list",
                        },
                        {
                          key: "notes",
                          label: "Notes",
                          type: "textarea",
                          max: 5000,
                        },
                      ],
                    })
                  }
                >
                  Update attendance and modules
                </button>
              )}
            </article>
          );
        })}
      {capacity && (
        <details>
          <summary className="cursor-pointer text-sm">
            Programme module reference
          </summary>
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {modules.map((module) => (
              <li key={module}>{module}</li>
            ))}
          </ul>
        </details>
      )}
      {!capacity && (
        <>
          {can("outcome:view") && can("outcome:edit") && (
            <button className="command primary" onClick={recordOutcome}>
              Record verified employment outcome
            </button>
          )}
          <p className="text-sm text-muted">
            Use the Placements workspace to create a recruitment placement and
            verify commencement and first income. Self-employment outcomes do
            not require a fabricated vacancy.
          </p>
          {placements.data?.map((item) => (
            <article
              key={item.id}
              className="rounded-lg border border-border p-4"
            >
              <h4 className="font-semibold">
                {String(item.placement_code)} ·{" "}
                {String(item.status).replaceAll("_", " ")}
              </h4>
              <Detail
                values={{
                  "PLACED BY PARTNER": item.placed_by_partner,
                  "PLACEMENT START DATE": item.actual_start_date,
                  "Age at Placement Start": item.age_at_placement_start,
                  "PLACEMENT REGION": item.placement_region,
                  "PLACEMENT DISTRICT": item.placement_district,
                  "PLACEMENT COMMUNITY": item.placement_community,
                  SECTOR: item.sector,
                  INDUSTRY: item.industry,
                  "JOB TYPE": item.job_type,
                  "JOB ROLE": item.job_role,
                  "EMPLOYMENT TYPE": item.employment_type,
                  "EMPLOYMENT CATEGORY": item.employment_category,
                  "PLACEMENT INCOME": item.salary_amount,
                  "PLACEMENT INCOME FREQ": item.salary_frequency,
                  "EMPLOYER NAME": item.employer_name ?? item.organization_name,
                  "CONTRACT TYPE": item.contract_type,
                  "WORK HOURS": item.work_hours,
                  "Hours period": item.work_hours_period,
                }}
              />
              {can("placement:edit") &&
                (!item.confirmed_at ||
                  can("placement:correct_confirmation")) && (
                  <button
                    className="command"
                    onClick={() =>
                      onEditor({
                        title: "Edit placement details",
                        path: `/placements/${item.id}/programme-details`,
                        method: "PATCH",
                        initial: item,
                        extra: { version: item.version },
                        fields: [
                          ...placementDetailFields,
                          {
                            key: "reason",
                            label: "Reason for update",
                            type: "textarea",
                            required: true,
                            max: 5000,
                          },
                        ],
                      })
                    }
                  >
                    Edit placement details
                  </button>
                )}
            </article>
          ))}
          <h4 className="font-semibold">Verified employment observations</h4>
          {outcomes.data?.length === 0 && (
            <p>No employment observations recorded.</p>
          )}
          {outcomes.data?.map((item) => (
            <article
              key={item.id}
              className="rounded-lg border border-border p-4"
            >
              <Detail
                values={{
                  "Observation Date": item.as_of_date,
                  "Employment Start Date": item.employment_start_date,
                  "Currently working": item.currently_working,
                  "Employment Type": item.employment_type,
                  "Employment Category": item.employment_category,
                  "Employer / business": item.current_employer,
                  "Job Role": item.current_role,
                  "Income (GHS)": item.current_income_amount,
                  "Income frequency": item.income_frequency,
                  "Income recording status": item.income_status,
                  ...Object.fromEntries(
                    Object.entries(
                      (item.agriculture ?? {}) as Record<string, unknown>,
                    )
                      .filter(([, value]) => value !== null)
                      .map(([key, value]) => [key.replaceAll("_", " "), value]),
                  ),
                }}
              />
            </article>
          ))}
        </>
      )}
    </section>
  );
}
