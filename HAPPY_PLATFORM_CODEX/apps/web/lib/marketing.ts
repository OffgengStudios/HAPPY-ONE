export type MarketingDashboard = {
  open_requests: number;
  in_production: number;
  scheduled: number;
  published: number;
  consent_pending_stories: number;
  ready_stories: number;
};

export type MarketingRequest = {
  id: string;
  version: number;
  request_code: string;
  requesting_workstream: string;
  request_type: string;
  vacancy_id: string | null;
  training_id: string | null;
  participant_id: string | null;
  reason: string;
  priority: string;
  status: string;
  due_at: string | null;
};

export type Campaign = {
  id: string;
  version: number;
  campaign_code: string;
  title: string;
  campaign_type: string;
  status: string;
  vacancy_id: string | null;
  training_id: string | null;
  marketing_request_id: string | null;
  audience: string;
  channels_json: string[];
  planned_publish_at: string | null;
  published_at: string | null;
  metrics_json: Record<string, string | number | null>;
};

export type CampaignAsset = {
  id: string;
  version: number;
  campaign_id: string;
  asset_type: string;
  title: string;
  external_url: string | null;
  content_text: string | null;
  approval_status: string;
  consent_id: string | null;
};

export type ImpactStory = {
  id: string;
  version: number;
  story_code: string;
  participant_name: string | null;
  source_outcome_id: string;
  marketing_consent_id: string | null;
  status: string;
  approved_quote: string | null;
  draft_text: string | null;
  approved_facts: {
    as_of_date: string;
    currently_working: boolean;
    current_role: string | null;
    skills_gained: string | null;
    progress: string | null;
  };
};

export type StoryCandidate = {
  id: string;
  as_of_date: string;
  currently_working: boolean;
  current_role: string | null;
  progress: string | null;
  skills_gained: string | null;
};
