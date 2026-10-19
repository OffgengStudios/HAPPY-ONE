import { Field } from "@/lib/demand";
import { label } from "@/lib/matching";

export type FirstIncome = {
  id: string;
  version: number;
  status: string;
  verification_due_date: string | null;
  actual_income_received_date: string | null;
  verified_at: string | null;
  amount_received: string | null;
  exception_reason: string | null;
  notes: string | null;
};

export type Placement = {
  id: string;
  version: number;
  placement_code: string;
  participant_id: string;
  candidate_vacancy_id: string;
  participant_name: string;
  participant_code: string;
  vacancy_title: string;
  organization_name: string;
  status: string;
  expected_start_date: string | null;
  actual_start_date: string | null;
  salary_amount: string | null;
  salary_currency: string;
  salary_frequency: string | null;
  payroll_frequency: string | null;
  expected_first_income_date: string | null;
  confirmed_at: string | null;
  employment_end_date: string | null;
  employment_end_reason: string | null;
  currently_working: boolean | null;
  owner_id: string | null;
  owner_name: string | null;
  first_income: FirstIncome;
};

const frequency = ["DAILY", "WEEKLY", "BIWEEKLY", "MONTHLY"].map((value) => ({
  value,
  label: label(value),
}));

export const placementFields: Field[] = [
  { key: "expected_start_date", label: "Expected start date", type: "date" },
  { key: "salary_amount", label: "Salary amount", type: "number", min: 0 },
  {
    key: "salary_frequency",
    label: "Salary frequency",
    type: "select",
    options: frequency,
  },
  {
    key: "payroll_frequency",
    label: "Payroll frequency",
    type: "select",
    options: frequency,
  },
  {
    key: "payroll_day",
    label: "Monthly payday",
    type: "number",
    min: 1,
    max: 31,
  },
  {
    key: "payroll_cutoff_day",
    label: "Monthly payroll cutoff",
    type: "number",
    min: 1,
    max: 31,
  },
  {
    key: "manual_first_income_date",
    label: "Manual first-income date",
    type: "date",
  },
  {
    key: "exception_reason",
    label: "Manual scheduling reason",
    type: "textarea",
    max: 5000,
  },
];
