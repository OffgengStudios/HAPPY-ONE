import { Field } from "./demand";

export type Participant = Record<string, unknown> & {
  id: string;
  version: number;
  full_name: string;
  participant_code: string;
  onboarding_status: string;
  readiness_status: string;
  availability_status: string;
  cv_status: string;
  archived_at: string | null;
  submission_eligible: boolean;
  policy_configured: boolean;
  privacy_notice_version: string | null;
  required_sections: string[];
  completed_sections: string[];
  missing_sections: string[];
  required_fields: string[];
  missing_fields: string[];
  profile_completion_pct: number;
};
export type SupplyItem = Record<string, unknown> & { id: string };
export type ParserSuggestion = {
  field: string;
  value: unknown;
  confidence: number | null;
};
export type ParserReview = {
  id: string;
  field: string;
  decision: "APPROVE" | "REJECT" | "EDIT";
  original_value: unknown;
  approved_value: unknown;
  confidence: number | null;
  reason: string | null;
};
export type ParserResult = {
  id: string;
  review_status: string;
  provider: string;
  model: string | null;
  suggestions: ParserSuggestion[];
  reviews: ParserReview[];
};
export type ParserJob = {
  id: string;
  status: string;
  provider: string | null;
  model: string | null;
  attempt_count: number;
  error_code: string | null;
  error_message: string | null;
  result: ParserResult | null;
};
export const label = (value: unknown) =>
  String(value ?? "Not recorded")
    .replaceAll("_", " ")
    .toLowerCase();
const text = (key: string, label: string, max = 150): Field => ({
  key,
  label,
  max,
});
const select = (key: string, label: string, values: string[]): Field => ({
  key,
  label,
  type: "select",
  required: true,
  options: values.map((value) => ({
    value,
    label: value.replaceAll("_", " ").toLowerCase(),
  })),
});
export const basicFields: Field[] = [
  { ...text("first_name", "First name", 100), required: true },
  { ...text("surname", "Surname", 100), required: true },
  text("other_names", "Other names", 100),
  text("implementing_partner", "Implementing partner"),
  { key: "onboarding_date", label: "Onboarding Date", type: "date" },
  text("support_type", "Participant Type - Support", 60),
  {
    key: "duplicate_acknowledged",
    label: "Reviewed as a distinct participant",
    type: "checkbox",
  },
];
export const contactFields: Field[] = [
  { key: "phone_raw", label: "Phone", type: "tel", required: true, max: 50 },
  { key: "email", label: "Email", type: "email", max: 254 },
  text("region_code", "Region", 60),
  text("district_code", "District", 60),
  { ...text("community", "Community"), required: true },
  text("location_status", "Location status", 60),
  { key: "directions", label: "Directions", type: "textarea", max: 5000 },
];
export const employmentFields: Field[] = [
  text("employment_status", "Employment status", 60),
  text("current_occupation", "Current occupation"),
  text("sector_code", "Sector", 60),
  text("industry_code", "Industry", 60),
  text("job_type", "Job type", 60),
  text("job_role", "Job role"),
  text("work_region_code", "Work region", 60),
  text("work_district_code", "Work district", 60),
  text("work_community", "Work community"),
];
export const educationFields: Field[] = [
  { ...text("education_level", "Education level", 100), required: true },
  text("institution", "Institution", 200),
  text("field_of_study", "Field of study", 200),
  {
    key: "start_year",
    label: "Start year",
    type: "number",
    min: 1900,
    max: 2100,
  },
  { key: "end_year", label: "End year", type: "number", min: 1900, max: 2100 },
  { key: "is_highest", label: "Highest qualification", type: "checkbox" },
];
export const experienceFields: Field[] = [
  { ...text("employer_name", "Employer", 200), required: true },
  { ...text("role_title", "Role", 200), required: true },
  { key: "start_date", label: "Start date", type: "date", required: true },
  { key: "end_date", label: "End date", type: "date" },
  text("sector", "Sector", 60),
  { key: "description", label: "Description", type: "textarea", max: 5000 },
];
export const skillFields: Field[] = [
  { ...text("skill_name", "Skill"), required: true },
  text("skill_code", "Skill code", 60),
  text("level", "Level", 60),
  text("source", "Skill source", 100),
  { key: "verified", label: "Verified by staff", type: "checkbox" },
];
export const reasonField: Field = {
  key: "reason",
  label: "Reason",
  type: "textarea",
  required: true,
  max: 5000,
};
export const readinessFields = [
  select("readiness_status", "Readiness", [
    "NOT_ASSESSED",
    "DEVELOPING",
    "JOB_READY",
    "NOT_JOB_READY",
  ]),
  select("availability_status", "Availability", [
    "UNKNOWN",
    "AVAILABLE",
    "TEMPORARILY_UNAVAILABLE",
    "UNAVAILABLE",
  ]),
  reasonField,
];
export const onboardingState = select("to_status", "Onboarding status", [
  "IN_PROGRESS",
  "BLOCKED",
  "WITHDRAWN",
]);
export const frequencies = ["MONTHLY", "WEEKLY", "DAILY", "HOURLY", "OTHER"];
export const sensitiveFields: Field[] = [
  {
    ...select("income_status", "Income recording status", [
      "KNOWN",
      "UNKNOWN",
      "NOT_RECORDED",
      "NOT_APPLICABLE",
    ]),
    required: false,
  },
  {
    ...select("refugee_status", "Refugee Status", ["YES", "NO", "UNKNOWN"]),
    required: false,
  },
  text("displacement_status", "Displacement status", 60),
  {
    key: "displacement_reason",
    label: "Displacement reason",
    type: "textarea",
    max: 5000,
  },
  text("original_community", "Original community"),
  text("host_community", "Host community"),
  {
    ...select("disability_status", "Disability Status", [
      "YES",
      "NO",
      "UNKNOWN",
    ]),
    required: false,
  },
  {
    key: "disability_specify",
    label: "Disability details",
    type: "textarea",
    max: 5000,
    showWhen: { key: "disability_status", value: "YES" },
  },
  {
    key: "current_income_amount",
    label: "Current income",
    type: "number",
    min: 0,
    step: "0.01",
  },
  {
    ...select("income_frequency", "Income frequency", frequencies),
    required: false,
  },
];
export const demographicFields: Field[] = [
  { key: "date_of_birth", label: "Date of birth", type: "date" },
  text("sex", "Sex", 60),
  {
    ...text("nationality", "Nationality (If Yes to Refugee)", 60),
    showWhen: { key: "refugee_status", value: "YES" },
  },
];
export const consentFields: Field[] = [
  select("consent_type", "Consent type", [
    "PROGRAMME",
    "MARKETING",
    "PUBLICATION",
  ]),
  select("method", "Recording method", [
    "WRITTEN",
    "VERBAL",
    "DIGITAL",
    "STAFF_RECORDED",
  ]),
  {
    key: "consented_at",
    label: "Consented (Ghana time)",
    type: "datetime-local",
    required: true,
  },
  {
    ...text("privacy_notice_version", "Privacy notice version", 100),
    required: true,
  },
  {
    key: "participant_agreed",
    label: "Participant agreed to the recorded notice",
    type: "checkbox",
  },
];
