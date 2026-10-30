export type DemandRecord = Record<string, unknown> & {
  id: string;
  version: number;
  status?: string;
  name?: string;
  title?: string;
  organization_id?: string;
  organization_name?: string;
  archived_at?: string | null;
  allowed_transitions?: string[];
  headcount?: {
    required: number;
    started: number;
    confirmed_placements: number;
    outstanding: number;
  };
};
export type DemandPage = { items: DemandRecord[]; next_cursor: string | null };
export type Owner = {
  id: string;
  full_name: string;
  demand: boolean;
  recruiter: boolean;
};
export type Field = {
  key: string;
  label: string;
  type?:
    | "text"
    | "email"
    | "tel"
    | "url"
    | "number"
    | "datetime-local"
    | "date"
    | "password"
    | "checkbox"
    | "textarea"
    | "json"
    | "list"
    | "select";
  required?: boolean;
  max?: number;
  min?: number;
  step?: string;
  options?: { value: string; label: string }[];
  showWhen?: { key: string; value: string };
  uiOnly?: boolean;
};
const text = (key: string, label: string, max = 150): Field => ({
  key,
  label,
  max,
});
const code = (key: string, label: string) => text(key, label, 60);
export const employerFields: Field[] = [
  { ...text("name", "Employer name", 200), required: true },
  { ...code("organization_type", "Organization type"), required: true },
  code("industry_code", "Industry code"),
  code("sector_code", "Sector code"),
  code("region_code", "Region code"),
  code("district_code", "District code"),
  text("community", "Community"),
  { key: "address_text", label: "Address", type: "textarea", max: 5000 },
  { key: "website", label: "Website", type: "url", max: 500 },
  { key: "relationship_owner_id", label: "Relationship owner", type: "select" },
  {
    key: "duplicate_acknowledged",
    label: "Distinct employer despite matching name",
    type: "checkbox",
  },
];
export const contactFields: Field[] = [
  { ...text("full_name", "Contact name"), required: true },
  text("job_title", "Job title"),
  { key: "phone_raw", label: "Phone", type: "tel", max: 50 },
  { key: "email", label: "Contact email", type: "email", max: 254 },
  { key: "is_primary", label: "Primary contact", type: "checkbox" },
  { key: "is_active", label: "Active contact", type: "checkbox" },
  { key: "notes", label: "Notes", type: "textarea", max: 5000 },
];
export const partnershipFields: Field[] = [
  {
    key: "partnership_type",
    label: "Partnership type",
    type: "select",
    required: true,
    options: ["TRAINING", "RECRUITMENT", "COMBINED"].map((value) => ({
      value,
      label: value,
    })),
  },
  { key: "start_date", label: "Start date", type: "date", required: true },
  { key: "end_date", label: "End date", type: "date" },
  { key: "mou_required", label: "MOU required", type: "checkbox" },
  { key: "priority", label: "Action priority", type: "select", required: true },
  {
    key: "mou_sent_at",
    label: "MOU sent (Ghana time)",
    type: "datetime-local",
  },
  {
    key: "mou_signed_at",
    label: "MOU signed (Ghana time)",
    type: "datetime-local",
  },
  { key: "owner_id", label: "Action owner", type: "select" },
  text("next_action", "Next action", 500),
  {
    key: "next_action_due_at",
    label: "Due (Ghana time)",
    type: "datetime-local",
  },
  { key: "reason", label: "Reason", type: "textarea", max: 5000 },
];
export const vacancyFields: Field[] = [
  { ...text("title", "Vacancy title", 200), required: true },
  {
    key: "required_headcount",
    label: "Positions required",
    type: "number",
    required: true,
    min: 1,
    max: 1000000,
    step: "1",
  },
  {
    key: "priority",
    label: "Priority",
    type: "select",
    required: true,
    options: ["NORMAL", "HIGH", "URGENT"].map((value) => ({
      value,
      label: value,
    })),
  },
  { key: "description", label: "Description", type: "textarea", max: 5000 },
  code("location_region_code", "Region code"),
  code("location_district_code", "District code"),
  text("location_community", "Community"),
  {
    key: "location_directions",
    label: "Directions",
    type: "textarea",
    max: 5000,
  },
  {
    key: "salary_min",
    label: "Minimum salary",
    type: "number",
    min: 0,
    step: "0.01",
  },
  {
    key: "salary_max",
    label: "Maximum salary",
    type: "number",
    min: 0,
    step: "0.01",
  },
  { ...text("salary_currency", "Currency", 3), required: true },
  {
    key: "salary_frequency",
    label: "Pay frequency",
    type: "select",
    options: ["HOURLY", "DAILY", "WEEKLY", "BIWEEKLY", "MONTHLY", "OTHER"].map(
      (value) => ({ value, label: value }),
    ),
  },
  text("work_days_text", "Work days"),
  text("work_hours_text", "Work hours"),
  {
    key: "accommodation_available",
    label: "Accommodation",
    type: "select",
    options: [
      { value: "true", label: "Available" },
      { value: "false", label: "Not available" },
    ],
  },
  { key: "demand_owner_id", label: "Demand owner", type: "select" },
  { key: "owner_id", label: "Recruiter", type: "select" },
];
export const reasonField: Field = {
  key: "reason",
  label: "Reason",
  type: "textarea",
  required: true,
  max: 5000,
};
export const requirementFields: Field[] = [
  { ...code("criterion_type", "Criterion type"), required: true },
  { ...text("criterion_key", "Criterion key", 100), required: true },
  {
    key: "operator",
    label: "Operator",
    type: "select",
    required: true,
    options: ["EQ", "IN", "GTE", "LTE"].map((value) => ({
      value,
      label: value,
    })),
  },
  {
    key: "value_json",
    label: "Value (JSON)",
    type: "json",
    required: true,
    max: 10000,
  },
  { key: "is_required", label: "Required criterion", type: "checkbox" },
  {
    key: "weight",
    label: "Weight",
    type: "number",
    min: 0,
    max: 999999,
    step: "0.01",
    required: true,
  },
  {
    key: "display_order",
    label: "Order",
    type: "number",
    min: 0,
    max: 10000,
    step: "1",
    required: true,
  },
  reasonField,
];
export function display(value: unknown): string {
  if (value === null || value === undefined || value === "")
    return "Not recorded";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
