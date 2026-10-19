import { Field } from "@/lib/demand";

export const stages = [
  "POTENTIAL_MATCH",
  "RECRUITER_REVIEW",
  "PRE_SCREEN",
  "QUALIFIED",
  "SUBMITTED",
  "INTERVIEW",
  "EMPLOYER_DECISION",
  "SELECTED",
] as const;

export type Candidate = {
  id: string;
  version: number;
  participant_id: string;
  participant_name: string;
  participant_code: string;
  onboarding_status: string;
  vacancy_id: string;
  vacancy_title: string;
  vacancy_status: string;
  organization_name: string;
  status: string;
  owner_id: string | null;
  owner_name: string | null;
  priority: string;
  next_action: string | null;
  next_action_due_at: string | null;
  pre_screen_result: string | null;
  submitted_at: string | null;
  selected_at: string | null;
  allowed_transitions: string[];
};

export type Interview = {
  id: string;
  version: number;
  candidate_vacancy_id: string;
  participant_name: string;
  vacancy_title: string;
  candidate_status: string;
  scheduled_at: string;
  format: string;
  location_or_link: string;
  status: string;
  outcome: string | null;
  notes: string | null;
};

export type Page<T> = { items: T[]; next_cursor: string | null };
export type Option = {
  id: string;
  full_name?: string;
  title?: string;
  name?: string;
};

export const label = (value: string) =>
  value
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/^./, (letter) => letter.toUpperCase());

export const candidateFields = (owners: Option[]): Field[] => [
  {
    key: "owner_id",
    label: "Recruiter",
    type: "select",
    options: owners.map((row) => ({
      value: row.id,
      label: row.full_name ?? row.id,
    })),
  },
  {
    key: "priority",
    label: "Priority",
    type: "select",
    required: true,
    options: ["NORMAL", "HIGH", "URGENT"].map((value) => ({
      value,
      label: label(value),
    })),
  },
  { key: "next_action", label: "Next action", max: 500 },
  {
    key: "next_action_due_at",
    label: "Due (Ghana time)",
    type: "datetime-local",
  },
];

export const screeningFields: Field[] = [
  {
    key: "result",
    label: "Screening result",
    type: "select",
    required: true,
    options: ["QUALIFIED", "NOT_QUALIFIED", "FOLLOW_UP"].map((value) => ({
      value,
      label: label(value),
    })),
  },
  {
    key: "participant_interested",
    label: "Participant is interested",
    type: "checkbox",
  },
  {
    key: "availability_confirmed",
    label: "Availability confirmed",
    type: "checkbox",
  },
  { key: "salary_accepted", label: "Salary accepted", type: "checkbox" },
  { key: "location_accepted", label: "Location accepted", type: "checkbox" },
  { key: "notes", label: "Screening notes", type: "textarea", max: 5000 },
];

export const interviewFields: Field[] = [
  {
    key: "scheduled_at",
    label: "Date and time (Ghana time)",
    type: "datetime-local",
    required: true,
  },
  {
    key: "format",
    label: "Format",
    type: "select",
    required: true,
    options: ["IN_PERSON", "PHONE", "VIDEO"].map((value) => ({
      value,
      label: label(value),
    })),
  },
  {
    key: "location_or_link",
    label: "Location or link",
    required: true,
    max: 1000,
  },
  { key: "notes", label: "Notes", type: "textarea", max: 5000 },
];
