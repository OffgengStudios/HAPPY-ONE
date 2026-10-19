export type Workstream =
  "demand" | "supply" | "matching" | "merl" | "marketing" | "management";

export type HealthStatus = {
  status: "ok";
  service: string;
  environment: string;
  request_id: string;
  checked_at: string;
};
