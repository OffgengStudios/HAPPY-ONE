"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BarChart3,
  ArrowLeft,
  FileText,
  Megaphone,
  Plus,
  RefreshCw,
  Send,
  Sparkles,
} from "lucide-react";
import { useState } from "react";
import { all, api, Me } from "@/lib/api";
import { Field } from "@/lib/demand";
import {
  Campaign,
  CampaignAsset,
  ImpactStory,
  MarketingDashboard,
  MarketingRequest,
  StoryCandidate,
} from "@/lib/marketing";
import { label } from "@/lib/matching";
import { SupplyItem } from "@/lib/supply";
import { DemandForm, Editor } from "./demand-form";

const options = (values: string[]) =>
  values.map((value) => ({ value, label: label(value) }));

export function MarketingWorkspace({
  view,
  user,
  initialIdentifier = null,
}: {
  view: string;
  user: Me;
  initialIdentifier?: string | null;
}) {
  const client = useQueryClient();
  const [editor, setEditor] = useState<Editor | null>(null);
  const [selectedCampaign, setSelectedCampaign] = useState<string | null>(
    initialIdentifier,
  );
  const section = view === "work" ? "requests" : view;
  const requests = useQuery({
    queryKey: ["marketing", "requests"],
    queryFn: () => all<MarketingRequest>("/marketing/requests"),
  });
  const campaigns = useQuery({
    queryKey: ["marketing", "campaigns"],
    queryFn: () => all<Campaign>("/campaigns"),
    enabled: user.permissions.includes("campaign:view"),
  });
  const stories = useQuery({
    queryKey: ["marketing", "stories"],
    queryFn: () => all<ImpactStory>("/impact-stories"),
    enabled: user.permissions.includes("impact_story:view"),
  });
  const candidates = useQuery({
    queryKey: ["marketing", "candidates"],
    queryFn: () => api<{ items: StoryCandidate[] }>("/impact-story-candidates"),
    enabled: user.permissions.includes("impact_story:edit"),
  });
  const dashboard = useQuery({
    queryKey: ["marketing", "dashboard"],
    queryFn: () => api<MarketingDashboard>("/marketing/dashboard"),
    enabled: user.permissions.includes("campaign:view"),
  });
  const vacancies = useQuery({
    queryKey: ["vacancies"],
    queryFn: () => all<SupplyItem>("/vacancies"),
    enabled: user.permissions.includes("vacancy:view"),
  });
  const trainings = useQuery({
    queryKey: ["trainings"],
    queryFn: () => all<SupplyItem>("/trainings"),
    enabled: user.permissions.includes("training:view"),
  });
  const assets = useQuery({
    queryKey: ["marketing", "campaign-assets", selectedCampaign],
    queryFn: () =>
      api<{ items: CampaignAsset[] }>(`/campaigns/${selectedCampaign}/assets`),
    enabled: Boolean(selectedCampaign),
  });
  const vacancyOptions = (vacancies.data ?? []).map((row) => ({
    value: String(row.id),
    label: String(row.title ?? row.vacancy_code),
  }));
  const trainingOptions = (trainings.data ?? []).map((row) => ({
    value: String(row.id),
    label: String(row.title ?? row.training_code),
  }));
  const requestOptions = (requests.data ?? []).map((row) => ({
    value: row.id,
    label: `${row.request_code} | ${label(row.request_type)}`,
  }));
  const campaignRows = [...(campaigns.data ?? [])].sort((left, right) =>
    left.id === initialIdentifier ? -1 : right.id === initialIdentifier ? 1 : 0,
  );
  const currentCampaign =
    campaignRows.find((row) => row.id === selectedCampaign) ?? null;
  const refresh = async () => {
    await client.invalidateQueries({ queryKey: ["marketing"] });
  };
  const requestCreate = () =>
    setEditor({
      title: "Create marketing request",
      path: "/marketing/requests",
      fields: [
        {
          key: "request_type",
          label: "Request type",
          type: "select",
          required: true,
          options: options([
            "VACANCY_PROMOTION",
            "TRAINING_PROMOTION",
            "PROGRAMME_AWARENESS",
            "IMPACT_STORY",
          ]),
        },
        {
          key: "vacancy_id",
          label: "Linked vacancy",
          type: "select",
          options: vacancyOptions,
        },
        {
          key: "training_id",
          label: "Linked training",
          type: "select",
          options: trainingOptions,
        },
        {
          key: "reason",
          label: "Reason",
          type: "textarea",
          required: true,
          max: 5000,
        },
        {
          key: "priority",
          label: "Priority",
          type: "select",
          required: true,
          options: options(["LOW", "NORMAL", "HIGH", "URGENT"]),
        },
        { key: "due_at", label: "Due date", type: "datetime-local" },
      ],
      initial: { priority: "NORMAL" },
    });
  const campaignCreate = () =>
    setEditor({
      title: "Create campaign",
      path: "/campaigns",
      fields: [
        { key: "title", label: "Campaign title", required: true, max: 200 },
        {
          key: "campaign_type",
          label: "Campaign type",
          type: "select",
          required: true,
          options: options([
            "RECRUITMENT",
            "TRAINING",
            "PROGRAMME_AWARENESS",
            "IMPACT_STORY",
          ]),
        },
        {
          key: "marketing_request_id",
          label: "Source request",
          type: "select",
          options: requestOptions,
        },
        {
          key: "vacancy_id",
          label: "Linked vacancy",
          type: "select",
          options: vacancyOptions,
        },
        {
          key: "training_id",
          label: "Linked training",
          type: "select",
          options: trainingOptions,
        },
        {
          key: "audience",
          label: "Audience",
          type: "textarea",
          required: true,
          max: 5000,
        },
        { key: "channels_json", label: "Channels", type: "json" },
        {
          key: "planned_publish_at",
          label: "Planned publication",
          type: "datetime-local",
        },
      ],
      initial: { channels_json: [] },
    });
  const campaignEdit = (row: Campaign) =>
    setEditor({
      title: "Edit campaign",
      path: `/campaigns/${row.id}`,
      method: "PATCH",
      fields: [
        { key: "title", label: "Campaign title", required: true, max: 200 },
        {
          key: "campaign_type",
          label: "Campaign type",
          type: "select",
          required: true,
          options: options([
            "RECRUITMENT",
            "TRAINING",
            "PROGRAMME_AWARENESS",
            "IMPACT_STORY",
          ]),
        },
        {
          key: "marketing_request_id",
          label: "Source request",
          type: "select",
          options: requestOptions,
        },
        {
          key: "vacancy_id",
          label: "Linked vacancy",
          type: "select",
          options: vacancyOptions,
        },
        {
          key: "training_id",
          label: "Linked training",
          type: "select",
          options: trainingOptions,
        },
        {
          key: "audience",
          label: "Audience",
          type: "textarea",
          required: true,
          max: 5000,
        },
        { key: "channels_json", label: "Channels", type: "json" },
        {
          key: "planned_publish_at",
          label: "Planned publication",
          type: "datetime-local",
        },
      ],
      initial: row,
      extra: { version: row.version },
    });
  const storyCreate = () =>
    setEditor({
      title: "Create impact story",
      path: "/impact-stories",
      fields: [
        {
          key: "source_outcome_id",
          label: "M&E story candidate",
          type: "select",
          required: true,
          options: (candidates.data?.items ?? []).map((row) => ({
            value: row.id,
            label: `${row.as_of_date} | ${row.current_role ?? "Verified outcome"}`,
          })),
        },
      ],
    });
  const assetCreate = (row: Campaign) =>
    setEditor({
      title: "Add campaign asset",
      path: `/campaigns/${row.id}/assets`,
      fields: [
        {
          key: "asset_type",
          label: "Asset type",
          type: "select",
          required: true,
          options: options([
            "SOCIAL_COPY",
            "FLYER",
            "PHOTO",
            "VIDEO_LINK",
            "REPORT_GRAPHIC",
          ]),
        },
        { key: "title", label: "Asset title", required: true, max: 200 },
        { key: "external_url", label: "External URL", type: "url" },
        {
          key: "content_text",
          label: "Copy or content",
          type: "textarea",
          max: 5000,
        },
      ],
    });
  const assetReview = (row: CampaignAsset) =>
    setEditor({
      title: "Review campaign asset",
      path: `/campaign-assets/${row.id}/review`,
      fields: [
        {
          key: "approval_status",
          label: "Review decision",
          type: "select",
          required: true,
          options: options(["AWAITING_REVIEW", "APPROVED", "REJECTED"]),
        },
        {
          key: "reason",
          label: "Review note",
          type: "textarea",
          required: true,
          max: 5000,
        },
      ],
      extra: { version: row.version },
    });
  const recordMetrics = (row: Campaign) =>
    setEditor({
      title: "Record campaign metrics",
      path: `/campaigns/${row.id}/metrics`,
      fields: [
        {
          key: "metrics",
          label: "Verified metrics",
          type: "json",
          required: true,
        },
      ],
      initial: { metrics: row.metrics_json },
      extra: { version: row.version },
    });
  const transition = (
    kind: "request" | "campaign" | "story",
    row: MarketingRequest | Campaign | ImpactStory,
  ) => {
    const states =
      kind === "request"
        ? [
            "ACCEPTED",
            "IN_PRODUCTION",
            "AWAITING_REVIEW",
            "APPROVED",
            "PUBLISHED",
            "COMPLETED",
            "CANCELLED",
          ]
        : kind === "campaign"
          ? [
              "IN_PRODUCTION",
              "AWAITING_REVIEW",
              "APPROVED",
              "SCHEDULED",
              "PUBLISHED",
              "COMPLETED",
              "CANCELLED",
            ]
          : [
              "CONSENT_PENDING",
              "READY_FOR_MARKETING",
              "DRAFTING",
              "REVIEW",
              "APPROVED",
              "PUBLISHED",
              "REJECTED",
              "CANCELLED",
            ];
    const root =
      kind === "request"
        ? "/marketing/requests"
        : kind === "campaign"
          ? "/campaigns"
          : "/impact-stories";
    setEditor({
      title: `Move ${kind}`,
      path: `${root}/${row.id}/transition`,
      fields: [
        {
          key: "status",
          label: "Next status",
          type: "select",
          required: true,
          options: options(states),
        },
        {
          key: "reason",
          label: "Reason",
          type: "textarea",
          required: true,
          max: 5000,
        },
      ],
      extra: { version: row.version },
    });
  };
  const openStory = async (row: ImpactStory) => {
    const result = await api<{
      items: {
        id: string;
        consent_type: string;
        privacy_notice_version: string;
      }[];
    }>(`/impact-stories/${row.id}/eligible-consents`);
    const fields: Field[] = [
      {
        key: "marketing_consent_id",
        label: "Marketing/publication consent",
        type: "select",
        options: result.items.map((item) => ({
          value: item.id,
          label: `${label(item.consent_type)} | ${item.privacy_notice_version}`,
        })),
      },
      {
        key: "approved_quote",
        label: "Approved quote",
        type: "textarea",
        max: 5000,
      },
      { key: "draft_text", label: "Story draft", type: "textarea", max: 5000 },
    ];
    setEditor({
      title: "Edit impact story",
      path: `/impact-stories/${row.id}`,
      method: "PATCH",
      fields,
      initial: row,
      extra: { version: row.version },
    });
  };
  const pending =
    requests.isPending ||
    campaigns.isPending ||
    stories.isPending ||
    dashboard.isPending;
  const queryError =
    requests.error || campaigns.error || stories.error || dashboard.error;
  return (
    <div className="min-w-0">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase text-primary">
            Marketing
          </p>
          <h2 className="mt-1 text-xl font-semibold">
            {section === "dashboard"
              ? "Marketing Dashboard"
              : section === "impact-stories"
                ? "Impact Stories"
                : label(section)}
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
          {section === "requests" &&
            user.permissions.includes("marketing_request:create") && (
              <button
                className="command primary"
                disabled={vacancies.isPending}
                onClick={requestCreate}
              >
                <Plus className="h-4 w-4" />
                New request
              </button>
            )}
          {section === "campaigns" &&
            !currentCampaign &&
            user.permissions.includes("campaign:edit") && (
              <button
                className="command primary"
                disabled={vacancies.isPending || requests.isPending}
                onClick={campaignCreate}
              >
                <Plus className="h-4 w-4" />
                New campaign
              </button>
            )}
          {section === "impact-stories" &&
            user.permissions.includes("impact_story:edit") && (
              <button
                className="command primary"
                disabled={!candidates.data?.items.length}
                onClick={storyCreate}
              >
                <Plus className="h-4 w-4" />
                New story
              </button>
            )}
        </div>
      </div>
      {pending && (
        <p role="status" className="py-6 text-sm text-muted">
          Loading marketing records...
        </p>
      )}
      {queryError && (
        <p role="alert" className="py-4 text-sm text-red-700">
          {queryError.message}
        </p>
      )}
      {section === "dashboard" && dashboard.data && (
        <MarketingDashboardView data={dashboard.data} />
      )}
      {section === "requests" && (
        <Rows empty="No marketing requests">
          {(requests.data ?? []).map((row) => (
            <button
              key={row.id}
              className="data-row flex w-full items-start justify-between gap-4 text-left"
              onClick={() =>
                user.permissions.includes("marketing_request:edit") &&
                transition("request", row)
              }
            >
              <span>
                <strong className="block text-sm">
                  {label(row.request_type)}
                </strong>
                <span className="mt-1 block text-xs text-muted">
                  {row.request_code} | {row.requesting_workstream}
                </span>
              </span>
              <span className="text-right text-xs text-muted">
                {label(row.status)}
                <span className="mt-1 block">{label(row.priority)}</span>
              </span>
            </button>
          ))}
        </Rows>
      )}
      {section === "campaigns" &&
        (currentCampaign ? (
          <section>
            <button
              className="command mb-5"
              onClick={() => setSelectedCampaign(null)}
            >
              <ArrowLeft className="h-4 w-4" />
              Back to campaigns
            </button>
            <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border pb-5">
              <div>
                <p className="text-xs text-muted">
                  {currentCampaign.campaign_code}
                </p>
                <h3 className="mt-1 text-lg font-semibold">
                  {currentCampaign.title}
                </h3>
                <p className="mt-2 text-sm text-muted">
                  {currentCampaign.audience}
                </p>
              </div>
              <span className="rounded border border-border bg-white px-2 py-1 text-xs">
                {label(currentCampaign.status)}
              </span>
            </div>
            {user.permissions.includes("campaign:edit") && (
              <div className="my-5 flex flex-wrap gap-2">
                <button
                  className="command primary"
                  onClick={() => transition("campaign", currentCampaign)}
                >
                  <Send className="h-4 w-4" />
                  Move campaign
                </button>
                <button
                  className="command"
                  onClick={() => campaignEdit(currentCampaign)}
                >
                  Edit campaign
                </button>
                <button
                  className="command"
                  onClick={() => assetCreate(currentCampaign)}
                >
                  <Plus className="h-4 w-4" />
                  Add asset
                </button>
                {["PUBLISHED", "COMPLETED"].includes(
                  currentCampaign.status,
                ) && (
                  <button
                    className="command"
                    onClick={() => recordMetrics(currentCampaign)}
                  >
                    <BarChart3 className="h-4 w-4" />
                    Record metrics
                  </button>
                )}
              </div>
            )}
            <h4 className="mt-7 border-b border-border pb-3 text-sm font-semibold">
              Assets
            </h4>
            <Rows empty="No campaign assets">
              {(assets.data?.items ?? []).map((row) => (
                <button
                  key={row.id}
                  className="data-row flex w-full items-start justify-between gap-4 text-left"
                  onClick={() =>
                    user.permissions.includes("campaign:edit") &&
                    assetReview(row)
                  }
                >
                  <span>
                    <strong className="flex items-center gap-2 text-sm">
                      <FileText className="h-4 w-4" />
                      {row.title}
                    </strong>
                    <span className="mt-1 block text-xs text-muted">
                      {label(row.asset_type)}
                    </span>
                  </span>
                  <span className="text-xs text-muted">
                    {label(row.approval_status)}
                  </span>
                </button>
              ))}
            </Rows>
          </section>
        ) : (
          <Rows empty="No campaigns">
            {campaignRows.map((row) => (
              <button
                key={row.id}
                className="data-row flex w-full items-start justify-between gap-4 text-left"
                onClick={() => setSelectedCampaign(row.id)}
              >
                <span>
                  <strong className="block text-sm">{row.title}</strong>
                  <span className="mt-1 block text-xs text-muted">
                    {row.campaign_code} | {row.audience}
                  </span>
                </span>
                <span className="text-xs text-muted">{label(row.status)}</span>
              </button>
            ))}
          </Rows>
        ))}
      {section === "impact-stories" && (
        <Rows empty="No impact stories">
          {(stories.data ?? []).map((row) => (
            <div
              key={row.id}
              className="data-row flex items-start justify-between gap-4"
            >
              <button
                className="min-w-0 text-left"
                onClick={() => void openStory(row)}
              >
                <strong className="block text-sm">
                  {row.participant_name ?? "Identity withheld pending consent"}
                </strong>
                <span className="mt-1 block text-xs text-muted">
                  {row.approved_facts.current_role ?? "Verified outcome"} |{" "}
                  {row.approved_facts.as_of_date}
                </span>
              </button>
              {user.permissions.includes("impact_story:edit") && (
                <button
                  className="command"
                  onClick={() => transition("story", row)}
                >
                  <Send className="h-4 w-4" />
                  {label(row.status)}
                </button>
              )}
            </div>
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
      {Array.isArray(children) && children.length ? (
        children
      ) : (
        <p className="border-b border-border py-8 text-sm text-muted">
          {empty}
        </p>
      )}
    </div>
  );
}

function MarketingDashboardView({ data }: { data: MarketingDashboard }) {
  const rows = [
    ["Open requests", data.open_requests, Megaphone],
    ["In production", data.in_production, Sparkles],
    ["Scheduled", data.scheduled, Send],
    ["Published", data.published, BarChart3],
    ["Consent pending", data.consent_pending_stories, Sparkles],
    ["Ready stories", data.ready_stories, Send],
  ] as const;
  return (
    <dl className="grid border-l border-t border-border sm:grid-cols-2 lg:grid-cols-3">
      {rows.map(([name, value, Icon]) => (
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
