"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, Me } from "@/lib/api";

type Operation = {
  id: string;
  source: string;
  status: string;
  received_at: string;
  participant_id?: string;
  employer_submission_id?: string;
  document_id?: string;
  error_code?: string;
  attempt_count?: number;
};

export function IntakeOperations({ user }: { user: Me }) {
  const client = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const [existing, setExisting] = useState("");
  const [reason, setReason] = useState("");
  const list = useQuery({
    queryKey: ["intake-operations"],
    queryFn: () => api<{ items: Operation[] }>("/intake-operations"),
  });
  const detail = useQuery({
    queryKey: ["intake-operations", selected],
    queryFn: () =>
      api<{
        id: string;
        status: string;
        payload: unknown;
        documents: { id: string; kind: string; scan_status: string }[];
      }>(`/intake-operations/${selected}`),
    enabled: !!selected,
  });
  const action = useMutation({
    mutationFn: ({ path, body }: { path: string; body: unknown }) =>
      api(path, "POST", body),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ["intake-operations"] });
      setReason("");
    },
  });
  return (
    <section>
      <h2 className="text-xl font-semibold">Integration operations</h2>
      <p className="mt-2 text-sm text-muted">
        Public submissions, duplicate reviews and CV processing. Access is
        restricted to authorized staff.
      </p>
      <button className="command mt-4" onClick={() => void list.refetch()}>
        Refresh operations
      </button>
      {list.error && <p role="alert">{list.error.message}</p>}
      {action.error && <p role="alert">{action.error.message}</p>}
      <div className="mt-4 divide-y divide-border">
        {list.data?.items.map((row) => (
          <div
            key={row.source + row.id}
            className="flex flex-wrap items-center gap-3 py-4"
          >
            <div className="min-w-0 flex-1">
              <strong className="text-sm">
                {row.source.replaceAll("_", " ")}
              </strong>
              <p className="break-all text-xs text-muted">{row.id}</p>
              <p className="text-xs">
                {row.status} · {new Date(row.received_at).toLocaleString()}
                {row.error_code ? ` · ${row.error_code}` : ""}
                {row.attempt_count ? ` · Attempt ${row.attempt_count}` : ""}
              </p>
            </div>
            {row.source !== "CV_PARSER" && (
              <button className="command" onClick={() => setSelected(row.id)}>
                Review submission
              </button>
            )}
            {row.source === "CV_PARSER" &&
              row.status === "FAILED" &&
              user.permissions.includes("cv_parse:run") && (
                <button
                  className="command"
                  disabled={action.isPending}
                  onClick={() =>
                    action.mutate({
                      path: `/cv/${row.document_id}/parse`,
                      body: {},
                    })
                  }
                >
                  Retry parsing
                </button>
              )}
          </div>
        ))}
      </div>
      {selected && detail.data && (
        <div className="mt-6 border border-border p-4">
          <h3 className="font-semibold">Submission evidence</h3>
          <pre className="my-4 max-h-80 overflow-auto whitespace-pre-wrap break-words text-xs">
            {JSON.stringify(detail.data.payload, null, 2)}
          </pre>
          {detail.data.documents.map((doc) => (
            <div
              className="my-2 flex flex-wrap items-center gap-2"
              key={doc.id}
            >
              <span>
                {doc.kind}: {doc.scan_status}
              </span>
              {doc.scan_status === "SCANNING" &&
                user.permissions.includes("integration_event:manage") && (
                  <button
                    className="command"
                    onClick={() =>
                      action.mutate({
                        path: `/intake-operations/${selected}/documents/${doc.id}/rescan`,
                        body: {},
                      })
                    }
                  >
                    Retry security scan
                  </button>
                )}
            </div>
          ))}
          {detail.data.status === "NEEDS_REVIEW" &&
            user.permissions.includes("integration_event:manage") && (
              <div className="space-y-3">
                <label className="block text-sm">
                  Review reason
                  <textarea
                    className="field mt-1"
                    value={reason}
                    onChange={(event) => setReason(event.target.value)}
                  />
                </label>
                <label className="block text-sm">
                  Existing HAPPY participant UUID
                  <input
                    className="field mt-1"
                    value={existing}
                    onChange={(event) => setExisting(event.target.value)}
                  />
                </label>
                <button
                  className="command"
                  disabled={
                    !reason.trim() || !existing.trim() || action.isPending
                  }
                  onClick={() =>
                    action.mutate({
                      path: `/intake-operations/${selected}/resolve`,
                      body: { existing_participant_id: existing, reason },
                    })
                  }
                >
                  Link reviewed duplicate
                </button>
                <button
                  className="command"
                  disabled={!reason.trim() || action.isPending}
                  onClick={() =>
                    action.mutate({
                      path: `/intake-operations/${selected}/review`,
                      body: { decision: "REJECT", reason },
                    })
                  }
                >
                  Reject submission
                </button>
              </div>
            )}
          <button className="command mt-3" onClick={() => setSelected(null)}>
            Close evidence
          </button>
        </div>
      )}
    </section>
  );
}
