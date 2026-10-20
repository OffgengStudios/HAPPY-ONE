"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, Check, Inbox, RefreshCw, X } from "lucide-react";
import { useState } from "react";
import { all, api } from "@/lib/api";

type Submission = {
  id: string;
  submission_id: string;
  reference_number: string | null;
  company_name: string;
  vacancy_count: number;
  status: string;
  review_notes: string | null;
  organization_id: string | null;
  received_at: string;
  version: number;
  possible_duplicates?: { id: string; name: string; reasons: string[] }[];
  documents?: { id: string; kind: string; scan_status: string }[];
  submission?: {
    sector: string | null;
    industry?: string | null;
    district?: string | null;
    address?: string | null;
    partnership_type?: string;
    company_size: string | null;
    region: string | null;
    city: string | null;
    website: string | null;
    contact_name: string;
    contact_role: string | null;
    contact_phone: string;
    contact_email: string;
    vacancies: {
      vacancy_id: string | null;
      job_title: string;
      location: string;
      employment_type: string;
      openings: number;
      compensation: string | null;
      description: string | null;
      salary_min?: string | null;
      salary_max?: string | null;
      salary_frequency?: string | null;
      work_days?: string | null;
      work_hours?: string | null;
      benefits?: string[];
      accommodation?: boolean | null;
      requirements?: { criterion_type: string; value_json: unknown }[];
    }[];
  };
};

type Employer = { id: string; name: string };

export function EmployerSubmissionWorkspace() {
  const client = useQueryClient();
  const [status, setStatus] = useState("NEW");
  const [selected, setSelected] = useState<string | null>(null);
  const [organizationId, setOrganizationId] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const list = useQuery({
    queryKey: ["employer-submissions", status],
    queryFn: () =>
      all<Submission>(
        "/integrations/employer-portal/submissions" +
          (status ? `?status=${encodeURIComponent(status)}` : ""),
      ),
  });
  const detail = useQuery({
    queryKey: ["employer-submissions", "detail", selected],
    queryFn: () =>
      api<Submission>(`/integrations/employer-portal/submissions/${selected}`),
    enabled: !!selected,
  });
  const employers = useQuery({
    queryKey: ["employer-submissions", "employers"],
    queryFn: () => all<Employer>("/organizations"),
    enabled: !!selected,
  });
  const mutate = useMutation({
    mutationFn: ({ path, body }: { path: string; body: unknown }) =>
      api<Submission>(path, "POST", body),
    onSuccess: async () => {
      setSelected(null);
      setOrganizationId("");
      setReason("");
      setError("");
      await client.invalidateQueries({ queryKey: ["employer-submissions"] });
      await client.invalidateQueries({ queryKey: ["demand"] });
    },
    onError: (problem: Error) => setError(problem.message),
  });
  const row = detail.data;
  function act(action: "convert" | "review", decision?: string) {
    if (!row || !reason.trim()) {
      setError("Record a review reason before continuing.");
      return;
    }
    mutate.mutate({
      path: `/integrations/employer-portal/submissions/${row.id}/${action}`,
      body:
        action === "convert"
          ? {
              version: row.version,
              existing_organization_id: organizationId || null,
              mou_required: true,
              reason,
            }
          : { version: row.version, decision, reason },
    });
  }
  return (
    <section>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase text-primary">
            Employer acquisition
          </p>
          <h2 className="mt-1 text-xl font-semibold">Submission inbox</h2>
        </div>
        <button
          className="icon-button"
          title="Refresh"
          aria-label="Refresh submissions"
          onClick={() => void list.refetch()}
        >
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>
      <div
        className="mb-5 flex flex-wrap gap-1 border-b border-border"
        role="tablist"
      >
        {["NEW", "NEEDS_REVIEW", "CONVERTED", "REJECTED", "ARCHIVED", ""].map(
          (value) => (
            <button
              key={value || "ALL"}
              role="tab"
              aria-selected={status === value}
              className={
                "border-b-2 px-3 py-3 text-sm " +
                (status === value
                  ? "border-primary font-medium text-primary"
                  : "border-transparent text-muted")
              }
              onClick={() => {
                setStatus(value);
                setSelected(null);
              }}
            >
              {(value || "ALL").replaceAll("_", " ")}
            </button>
          ),
        )}
      </div>
      {list.isPending && <p role="status">Loading submissions...</p>}
      {list.error && <p role="alert">{list.error.message}</p>}
      {!list.isPending && list.data?.length === 0 && (
        <div className="flex min-h-44 flex-col items-center justify-center gap-3 border-y border-border text-muted">
          <Inbox className="h-6 w-6" aria-hidden="true" />
          <p className="text-sm">No submissions in this queue</p>
        </div>
      )}
      <div className="divide-y divide-border border-y border-border">
        {list.data?.map((item) => (
          <button
            key={item.id}
            className="flex w-full items-center justify-between gap-4 px-1 py-4 text-left hover:bg-surface"
            onClick={() => {
              setSelected(item.id);
              setReason("");
              setError("");
            }}
          >
            <span className="min-w-0">
              <strong className="block truncate text-sm">
                {item.company_name}
              </strong>
              <span className="text-xs text-muted">
                {item.reference_number ?? item.submission_id} ·{" "}
                {item.vacancy_count} vacancies
              </span>
            </span>
            <span className="text-xs font-medium text-primary">
              {item.status.replaceAll("_", " ")}
            </span>
          </button>
        ))}
      </div>
      {selected && (
        <div
          className="fixed inset-0 z-40"
          role="dialog"
          aria-modal="true"
          aria-label="Employer submission"
        >
          <button
            className="absolute inset-0 bg-black/40"
            aria-label="Close"
            onClick={() => setSelected(null)}
          />
          <aside className="absolute inset-y-0 right-0 w-full max-w-xl overflow-y-auto bg-white p-6 shadow-xl">
            <button
              className="icon-button float-right"
              aria-label="Close"
              onClick={() => setSelected(null)}
            >
              <X className="h-4 w-4" />
            </button>
            {detail.isPending && <p role="status">Loading submission...</p>}
            {detail.error && <p role="alert">{detail.error.message}</p>}
            {row?.submission && (
              <>
                <p className="text-xs font-semibold uppercase text-primary">
                  {row.reference_number ?? row.submission_id}
                </p>
                <h3 className="mt-1 text-xl font-semibold">
                  {row.company_name}
                </h3>
                <dl className="mt-5 grid gap-4 border-y border-border py-5 sm:grid-cols-2">
                  {[
                    ["Sector", row.submission.sector],
                    ["Region", row.submission.region],
                    ["District", row.submission.district],
                    ["Industry", row.submission.industry],
                    ["Partnership", row.submission.partnership_type],
                    ["Address", row.submission.address],
                    ["City", row.submission.city],
                    ["Company size", row.submission.company_size],
                    ["Contact", row.submission.contact_name],
                    ["Role", row.submission.contact_role],
                    ["Phone", row.submission.contact_phone],
                    ["Email", row.submission.contact_email],
                  ].map(([name, value]) => (
                    <div key={name} className="min-w-0">
                      <dt className="text-xs text-muted">{name}</dt>
                      <dd className="mt-1 break-words text-sm">
                        {value || "Not provided"}
                      </dd>
                    </div>
                  ))}
                </dl>
                <h4 className="mt-6 text-sm font-semibold">Vacancies</h4>
                <div className="mt-2 divide-y divide-border border-y border-border">
                  {row.submission.vacancies.map((vacancy, index) => (
                    <div className="py-3" key={vacancy.vacancy_id ?? index}>
                      <strong className="text-sm">{vacancy.job_title}</strong>
                      <p className="mt-1 text-xs text-muted">
                        {vacancy.location} ·{" "}
                        {vacancy.employment_type.replaceAll("_", " ")} ·{" "}
                        {vacancy.openings} openings
                      </p>
                      <p className="mt-1 text-xs text-muted">
                        Salary: {vacancy.salary_min ?? "Not provided"} to{" "}
                        {vacancy.salary_max ?? "Not provided"}{" "}
                        {vacancy.salary_frequency ?? ""}
                      </p>
                      <p className="mt-1 text-xs text-muted">
                        Schedule: {vacancy.work_days ?? "Not provided"}{" "}
                        {vacancy.work_hours ?? ""}
                      </p>
                      <p className="mt-1 text-xs text-muted">
                        Benefits:{" "}
                        {vacancy.benefits?.join(", ") || "Not provided"}
                      </p>
                      {vacancy.requirements?.map((item, i) => (
                        <p key={i} className="mt-1 break-words text-xs">
                          {item.criterion_type}: {String(item.value_json)}
                        </p>
                      ))}
                    </div>
                  ))}
                </div>
                {row.possible_duplicates &&
                  row.possible_duplicates.length > 0 && (
                    <div className="mt-4">
                      <h4 className="text-sm font-semibold">
                        Possible existing employers
                      </h4>
                      {row.possible_duplicates.map((item) => (
                        <p key={item.id} className="mt-1 text-sm">
                          {item.name} ({item.reasons.join(", ")})
                        </p>
                      ))}
                    </div>
                  )}
                {row.documents && row.documents.length > 0 && (
                  <div className="mt-4">
                    <h4 className="text-sm font-semibold">Private documents</h4>
                    {row.documents.map((doc) => (
                      <div
                        key={doc.id}
                        className="mt-2 flex flex-wrap items-center gap-2 text-sm"
                      >
                        <span>
                          {doc.kind}: {doc.scan_status}
                        </span>
                        {doc.scan_status === "AVAILABLE" && (
                          <a
                            className="command"
                            href={`/api/v1/integrations/employer-portal/submissions/${row.id}/documents/${doc.id}/download`}
                          >
                            Download {doc.kind}
                          </a>
                        )}
                      </div>
                    ))}
                  </div>
                )}
                {["NEW", "NEEDS_REVIEW"].includes(row.status) && (
                  <div className="mt-6 space-y-4">
                    <label className="block text-sm">
                      Existing employer
                      <select
                        className="field mt-1"
                        value={organizationId}
                        onChange={(event) =>
                          setOrganizationId(event.target.value)
                        }
                      >
                        <option value="">Create a new employer</option>
                        {employers.data?.map((employer) => (
                          <option key={employer.id} value={employer.id}>
                            {employer.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="block text-sm">
                      Review reason
                      <textarea
                        className="field mt-1 min-h-24"
                        maxLength={1000}
                        value={reason}
                        onChange={(event) => setReason(event.target.value)}
                      />
                    </label>
                    {error && (
                      <p role="alert" className="text-sm text-red-700">
                        {error}
                      </p>
                    )}
                    <div className="flex flex-wrap gap-2">
                      <button
                        className="command primary"
                        disabled={mutate.isPending}
                        onClick={() => act("convert")}
                      >
                        <Check className="h-4 w-4" />
                        Convert
                      </button>
                      <button
                        className="command"
                        disabled={mutate.isPending}
                        onClick={() => act("review", "REJECT")}
                      >
                        <X className="h-4 w-4" />
                        Reject
                      </button>
                      <button
                        className="command"
                        disabled={mutate.isPending}
                        onClick={() => act("review", "ARCHIVE")}
                      >
                        <Archive className="h-4 w-4" />
                        Archive
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}
          </aside>
        </div>
      )}
    </section>
  );
}
