export type SearchEntity =
  "PARTICIPANT" | "ORGANIZATION" | "VACANCY" | "PLACEMENT" | "CAMPAIGN";
export type SearchItem = {
  entity_type: SearchEntity;
  id: string;
  code: string;
  label: string;
  context: string | null;
};
export type SearchPage = { items: SearchItem[]; next_cursor: string | null };
export type SearchResult = {
  groups: Partial<Record<SearchEntity, SearchPage>>;
};
export const searchGroups: {
  type: SearchEntity;
  label: string;
  permission: string;
}[] = [
  {
    type: "PARTICIPANT",
    label: "Participants",
    permission: "participant:view",
  },
  { type: "ORGANIZATION", label: "Employers", permission: "organization:view" },
  { type: "VACANCY", label: "Vacancies", permission: "vacancy:view" },
  { type: "PLACEMENT", label: "Placements", permission: "placement:view" },
  { type: "CAMPAIGN", label: "Campaigns", permission: "campaign:view" },
];
