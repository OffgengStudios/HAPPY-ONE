"use client";

import { useQuery } from "@tanstack/react-query";
import { Check, LoaderCircle, RefreshCw, Sparkles } from "lucide-react";
import { useState } from "react";
import { api, Me } from "@/lib/api";
import { label, ParserJob, Participant, SupplyItem } from "@/lib/supply";

const display = (value: unknown) =>
  Array.isArray(value) ? value.join(", ") : String(value ?? "Not recorded");

export function CvParserPanel({
  document,
  participant,
  user,
  refresh,
}: {
  document: SupplyItem;
  participant: Participant;
  user: Me;
  refresh: () => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [decisions, setDecisions] = useState<
    Record<string, "APPROVE" | "REJECT" | "EDIT" | "">
  >({});
  const [edits, setEdits] = useState<Record<string, string>>({});
  const jobs = useQuery({
    queryKey: ["supply", "parser-jobs", document.id],
    queryFn: () =>
      api<{ items: ParserJob[] }>(`/cv/${document.id}/parser-jobs`),
    enabled: open && user.permissions.includes("cv_parse:view"),
  });
  const latest = jobs.data?.items[0];
  const result = latest?.result;
  const reviewed = new Set(result?.reviews.map((item) => item.field) ?? []);
  const pending =
    result?.suggestions.filter((item) => !reviewed.has(item.field)) ?? [];

  async function run() {
    setBusy(true);
    setError("");
    try {
      await api(`/cv/${document.id}/parse`, "POST");
      await Promise.all([jobs.refetch(), refresh()]);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Unable to parse CV.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function review() {
    if (!result || pending.some((item) => !decisions[item.field])) {
      setError("Choose a decision for every remaining suggestion.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api(`/cv-parser/results/${result.id}/review`, "POST", {
        participant_version: participant.version,
        decisions: pending.map((item) => ({
          field: item.field,
          decision: decisions[item.field],
          ...(decisions[item.field] === "EDIT"
            ? {
                value:
                  item.field === "skills"
                    ? (edits[item.field] ?? display(item.value))
                        .split(",")
                        .map((value) => value.trim())
                        .filter(Boolean)
                    : (edits[item.field] ?? display(item.value)),
                reason: "Reviewed and corrected by staff.",
              }
            : {}),
        })),
      });
      setDecisions({});
      setEdits({});
      await Promise.all([jobs.refetch(), refresh()]);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Unable to save review.",
      );
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  if (!user.permissions.includes("cv_parse:view")) return null;
  return (
    <div className="mt-3 border-t border-border pt-3">
      <button className="command" onClick={() => setOpen((value) => !value)}>
        <Sparkles className="h-4 w-4" />
        {open ? "Close parser review" : "Parser review"}
      </button>
      {open && (
        <div className="mt-4 border-l-2 border-accent pl-4">
          {jobs.isPending && (
            <p
              role="status"
              className="flex items-center gap-2 text-sm text-muted"
            >
              <LoaderCircle className="h-4 w-4 animate-spin" /> Loading...
            </p>
          )}
          {jobs.error && (
            <p role="alert" className="text-sm text-red-700">
              {jobs.error.message}
            </p>
          )}
          {!jobs.isPending &&
            !latest &&
            user.permissions.includes("cv_parse:run") && (
              <button
                className="command"
                disabled={busy}
                onClick={() => void run()}
              >
                {busy ? (
                  <LoaderCircle className="h-4 w-4 animate-spin" />
                ) : (
                  <Sparkles className="h-4 w-4" />
                )}
                Parse CV
              </button>
            )}
          {latest?.status === "FAILED" && (
            <div>
              <p role="status" className="text-sm text-red-700">
                {latest.error_message ?? "CV parsing failed."}
              </p>
              {user.permissions.includes("cv_parse:run") && (
                <button
                  className="command mt-3"
                  disabled={busy}
                  onClick={() => void run()}
                >
                  <RefreshCw className="h-4 w-4" /> Retry
                </button>
              )}
            </div>
          )}
          {result && (
            <div className="space-y-4">
              <p className="text-xs text-muted">
                {label(result.review_status)} | {result.provider}
                {result.model ? ` / ${result.model}` : ""}
              </p>
              {result.suggestions.map((suggestion) => {
                const prior = result.reviews.find(
                  (item) => item.field === suggestion.field,
                );
                return (
                  <div
                    key={suggestion.field}
                    className="grid gap-3 border-y border-border py-3 md:grid-cols-3"
                  >
                    <div>
                      <p className="text-xs text-muted capitalize">
                        Current {label(suggestion.field)}
                      </p>
                      <p className="mt-1 break-words text-sm">
                        {display(participant[suggestion.field])}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-muted">Parser suggestion</p>
                      <p className="mt-1 break-words text-sm">
                        {display(suggestion.value)}
                      </p>
                      <p className="mt-1 text-xs text-muted">
                        {suggestion.confidence === null
                          ? "Confidence not supplied"
                          : `${Math.round(suggestion.confidence * 100)}% confidence`}
                      </p>
                    </div>
                    <div>
                      {prior ? (
                        <p className="text-sm capitalize">
                          {label(prior.decision)}
                        </p>
                      ) : (
                        <>
                          <label
                            className="field-label"
                            htmlFor={`parser-${document.id}-${suggestion.field}`}
                          >
                            Decision
                          </label>
                          <select
                            id={`parser-${document.id}-${suggestion.field}`}
                            value={decisions[suggestion.field] ?? ""}
                            onChange={(event) =>
                              setDecisions((current) => ({
                                ...current,
                                [suggestion.field]: event.target.value as
                                  "APPROVE" | "REJECT" | "EDIT" | "",
                              }))
                            }
                          >
                            <option value="">Choose</option>
                            <option value="APPROVE">Approve</option>
                            <option value="REJECT">Reject</option>
                            <option value="EDIT">Edit</option>
                          </select>
                          {decisions[suggestion.field] === "EDIT" && (
                            <input
                              className="mt-2"
                              aria-label={`Edited ${label(suggestion.field)}`}
                              value={
                                edits[suggestion.field] ??
                                display(suggestion.value)
                              }
                              onChange={(event) =>
                                setEdits((current) => ({
                                  ...current,
                                  [suggestion.field]: event.target.value,
                                }))
                              }
                            />
                          )}
                        </>
                      )}
                    </div>
                  </div>
                );
              })}
              {pending.length > 0 &&
                user.permissions.includes("cv_parse:review") && (
                  <button
                    className="primary"
                    disabled={busy}
                    onClick={() => void review()}
                  >
                    <Check className="h-4 w-4" /> Save review
                  </button>
                )}
            </div>
          )}
          {error && (
            <p role="alert" className="mt-3 text-sm text-red-700">
              {error}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
