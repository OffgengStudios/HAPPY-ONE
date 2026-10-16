export type MerlDashboard = {
  scheduled: number;
  due: number;
  overdue: number;
  completed: number;
  latest_verified_working: number;
  impact_story_candidates: number;
  open_data_quality: number;
};

export type FollowUp = {
  id: string;
  version: number;
  follow_up_code: string;
  participant_id: string;
  participant_name: string;
  placement_id: string;
  follow_up_type: string;
  scheduled_for: string;
  status: string;
  contact_result: string | null;
  notes: string | null;
};

export type Outcome = {
  id: string;
  version: number;
  participant_name: string;
  placement_id: string;
  follow_up_id: string | null;
  as_of_date: string;
  currently_working: boolean;
  current_employer: string | null;
  current_role: string | null;
  job_satisfaction: number | null;
  progress_text: string | null;
  support_needed_text: string | null;
  impact_story_potential: boolean;
};

export type DataQualityIssue = {
  id: string;
  version: number;
  issue_code: string;
  entity_type: string;
  entity_id: string;
  issue_type: string;
  severity: string;
  status: string;
  description: string;
  owner_id: string | null;
};
