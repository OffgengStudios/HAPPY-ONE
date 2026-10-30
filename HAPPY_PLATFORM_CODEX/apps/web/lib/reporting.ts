export type Kpi = {
  code: string;
  label: string;
  value: string | null;
  numerator: number | null;
  denominator: number | null;
  available: boolean;
  unavailable_reason: string | null;
  basis: string;
  target: string | null;
  gap: string | null;
  forecast: string | null;
  has_drilldown: boolean;
};

export type ReportingDashboard = {
  period: { date_from: string; date_to: string };
  metrics: Kpi[];
  placement_trend: { month: string; confirmed_placements: number }[];
  attention: {
    overdue_first_income: number;
    overdue_follow_ups: number;
    critical_data_quality: number;
    campaigns_awaiting_review: number;
  };
};

export type ReportTarget = {
  id: string;
  version: number;
  kpi_code: string;
  period_start: string;
  period_end: string;
  dimension_key: "GLOBAL";
  target_value: string;
  forecast_value: string | null;
  notes: string | null;
};

export type DrilldownRow = Record<string, string | number | boolean | null>;

export type ReportExportJob = {
  id: string;
  version: number;
  kpi_code: string;
  period_start: string;
  period_end: string;
  status: "PENDING" | "RUNNING" | "SUCCEEDED" | "FAILED";
  include_sensitive: boolean;
  row_count: number | null;
  error_message: string | null;
  created_at: string;
};
