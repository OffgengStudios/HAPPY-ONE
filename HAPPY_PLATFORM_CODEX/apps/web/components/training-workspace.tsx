"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Pencil, Plus, RefreshCw, Users } from "lucide-react";
import { useState } from "react";
import { all, api, Me } from "@/lib/api";
import { label, Participant } from "@/lib/supply";
import { DemandForm, Editor } from "./demand-form";
import { Dialog } from "./dialog";

type Attendance = {
  id: string;
  participant_id: string;
  attendance_status: string;
  completion_status: string;
  certificate_issued: boolean;
  notes: string | null;
  version: number;
};

type Training = {
  id: string;
  training_code: string;
  title: string;
  training_type: string;
  partner_organization_id: string | null;
  trainer_type: string;
  mode: string;
  start_date: string;
  end_date: string | null;
  location_text: string | null;
  virtual_platform: string | null;
  modules_json: string[];
  status: string;
  version: number;
  attendance?: Attendance[];
};

type Organization = { id: string; name: string };

const options = (values: string[]) =>
  values.map((value) => ({ value, label: label(value) }));

export function TrainingWorkspace({ user }: { user: Me }) {
  const client = useQueryClient();
  const canEdit = user.permissions.includes("training:edit");
  const [selected, setSelected] = useState<string | null>(null);
  const [editor, setEditor] = useState<Editor | null>(null);
  const [enrolling, setEnrolling] = useState(false);
  const [participantId, setParticipantId] = useState("");
  const [error, setError] = useState("");
  const trainings = useQuery({
    queryKey: ["trainings"],
    queryFn: () => all<Training>("/trainings"),
  });
  const detail = useQuery({
    queryKey: ["trainings", selected],
    queryFn: () => api<Training>(`/trainings/${selected}`),
    enabled: !!selected,
  });
  const participants = useQuery({
    queryKey: ["training-participants"],
    queryFn: () => all<Participant>("/participants"),
    enabled: user.permissions.includes("participant:view"),
  });
  const organizations = useQuery({
    queryKey: ["training-organizations"],
    queryFn: () => all<Organization>("/organizations"),
    enabled: canEdit && user.permissions.includes("organization:view"),
  });
  const enrol = useMutation({
    mutationFn: () =>
      api<{ items: Attendance[] }>(
        `/trainings/${selected}/participants`,
        "POST",
        { participant_ids: [participantId] },
      ),
    onSuccess: async () => {
      setEnrolling(false);
      setParticipantId("");
      setError("");
      await client.invalidateQueries({ queryKey: ["trainings", selected] });
    },
    onError: (problem: Error) => setError(problem.message),
  });
  const participantName = (id: string) => {
    const row = participants.data?.find((item) => item.id === id);
    return row ? `${row.full_name} · ${row.participant_code}` : id;
  };
  const editTraining = (row?: Training) =>
    setEditor({
      title: row ? "Edit training" : "New training",
      path: row ? `/trainings/${row.id}` : "/trainings",
      method: row ? "PATCH" : "POST",
      initial: row ?? { modules_json: [] },
      extra: row ? { version: row.version } : undefined,
      fields: [
        { key: "title", label: "Training title", required: true, max: 200 },
        { key: "agriculture_sector", label: "Agriculture Sector", max: 60 },
        {
          key: "training_type",
          label: "Training type",
          required: true,
          max: 60,
        },
        {
          key: "trainer_type",
          label: "Trainer type",
          type: "select",
          required: true,
          options: options(["INTERNAL", "EXTERNAL_PARTNER"]),
        },
        {
          key: "partner_organization_id",
          label: "Training partner",
          type: "select",
          options: organizations.data?.map((item) => ({
            value: item.id,
            label: item.name,
          })),
        },
        {
          key: "mode",
          label: "Delivery mode",
          type: "select",
          required: true,
          options: options(["IN_PERSON", "VIRTUAL", "HYBRID"]),
        },
        {
          key: "start_date",
          label: "Start date",
          type: "date",
          required: true,
        },
        { key: "end_date", label: "End date", type: "date" },
        { key: "location_region_code", label: "Region code", max: 60 },
        { key: "location_district_code", label: "District code", max: 60 },
        { key: "location_community", label: "Community", max: 200 },
        { key: "location_text", label: "Location", max: 5000 },
        { key: "virtual_platform", label: "Virtual platform", max: 120 },
        {
          key: "modules_json",
          label: "Planned modules (one per line)",
          type: "list",
          required: true,
        },
        {
          key: "status",
          label: "Status",
          type: "select",
          required: true,
          options: options([
            "DRAFT",
            "PLANNED",
            "IN_PROGRESS",
            "COMPLETED",
            "CANCELLED",
          ]),
        },
      ],
    });
  const editAttendance = (row: Attendance) =>
    setEditor({
      title: "Update attendance",
      path: `/training-attendance/${row.id}`,
      method: "PATCH",
      initial: row,
      extra: { version: row.version },
      fields: [
        {
          key: "received_modules",
          label: "Modules received (one per line)",
          type: "list",
        },
        {
          key: "completed_modules",
          label: "Modules completed (one per line)",
          type: "list",
        },
        {
          key: "attendance_status",
          label: "Attendance",
          type: "select",
          required: true,
          options: options(["PRESENT", "ABSENT", "LATE", "EXCUSED"]),
        },
        {
          key: "completion_status",
          label: "Completion",
          type: "select",
          required: true,
          options: options([
            "NOT_STARTED",
            "IN_PROGRESS",
            "COMPLETED",
            "NOT_COMPLETED",
          ]),
        },
        { key: "notes", label: "Notes", type: "textarea", max: 5000 },
      ],
    });
  const refresh = async () => {
    await client.invalidateQueries({ queryKey: ["trainings"] });
    await client.invalidateQueries({ queryKey: ["training-participants"] });
  };
  return (
    <div className="min-w-0">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase text-primary">
            Capacity building
          </p>
          <h2 className="mt-1 text-xl font-semibold">Training</h2>
        </div>
        <div className="flex gap-2">
          <button
            className="icon-button"
            title="Refresh"
            aria-label="Refresh training"
            onClick={() => void refresh()}
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          {canEdit && (
            <button className="command primary" onClick={() => editTraining()}>
              <Plus className="h-4 w-4" /> New training
            </button>
          )}
        </div>
      </div>
      {trainings.isPending && <p role="status">Loading training...</p>}
      {trainings.error && <p role="alert">{trainings.error.message}</p>}
      {!trainings.isPending && trainings.data?.length === 0 && (
        <div className="flex min-h-44 flex-col items-center justify-center gap-3 border-y border-border text-muted">
          <Users className="h-6 w-6" aria-hidden="true" />
          <p className="text-sm">No training sessions</p>
        </div>
      )}
      <div className="divide-y divide-border border-y border-border">
        {trainings.data?.map((row) => (
          <button
            key={row.id}
            className="flex w-full items-center justify-between gap-4 px-1 py-4 text-left hover:bg-surface"
            onClick={() => setSelected(row.id)}
          >
            <span className="min-w-0">
              <strong className="block truncate text-sm">{row.title}</strong>
              <span className="text-xs text-muted">
                {row.training_code} · {row.start_date} · {label(row.mode)}
              </span>
            </span>
            <span className="text-xs font-medium text-primary">
              {label(row.status)}
            </span>
          </button>
        ))}
      </div>
      {selected && (
        <Dialog
          title="Training details"
          placement="action"
          onClose={() => setSelected(null)}
        >
          <div className="space-y-5 p-5">
            {detail.isPending && (
              <p role="status">Loading training details...</p>
            )}
            {detail.error && <p role="alert">{detail.error.message}</p>}
            {detail.data && (
              <>
                <div>
                  <p className="text-xs font-semibold uppercase text-primary">
                    {detail.data.training_code}
                  </p>
                  <h3 className="mt-1 text-lg font-semibold">
                    {detail.data.title}
                  </h3>
                  <p className="mt-2 text-sm text-muted">
                    {label(detail.data.training_type)} ·{" "}
                    {label(detail.data.mode)} · {detail.data.start_date}
                  </p>
                  {canEdit && (
                    <button
                      className="command mt-4"
                      onClick={() => editTraining(detail.data)}
                    >
                      <Pencil className="h-4 w-4" /> Edit training
                    </button>
                  )}
                </div>
                <div className="flex items-center justify-between gap-3 border-b border-border pb-3">
                  <h4 className="text-sm font-semibold">Attendance</h4>
                  {canEdit && (
                    <button
                      className="command"
                      onClick={() => {
                        setEnrolling(true);
                        setError("");
                      }}
                    >
                      <Plus className="h-4 w-4" /> Add participant
                    </button>
                  )}
                </div>
                {detail.data.attendance?.length === 0 && (
                  <p className="text-sm text-muted">No participants enrolled</p>
                )}
                <div className="divide-y divide-border">
                  {detail.data.attendance?.map((row) => (
                    <button
                      key={row.id}
                      disabled={!canEdit}
                      className="flex w-full items-center justify-between gap-3 py-3 text-left disabled:cursor-default"
                      onClick={() => canEdit && editAttendance(row)}
                    >
                      <span className="min-w-0 text-sm">
                        {participantName(row.participant_id)}
                      </span>
                      <span className="shrink-0 text-xs text-muted">
                        {label(row.attendance_status)} ·{" "}
                        {label(row.completion_status)}
                      </span>
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        </Dialog>
      )}
      {enrolling && (
        <Dialog
          title="Add participant"
          placement="action"
          onClose={() => setEnrolling(false)}
        >
          <form
            className="space-y-5 p-5"
            onSubmit={(event) => {
              event.preventDefault();
              enrol.mutate();
            }}
          >
            <label className="field-label">
              Participant
              <select
                className="field"
                required
                value={participantId}
                onChange={(event) => setParticipantId(event.target.value)}
              >
                <option value="">Select participant</option>
                {participants.data
                  ?.filter(
                    (item) =>
                      !detail.data?.attendance?.some(
                        (row) => row.participant_id === item.id,
                      ),
                  )
                  .map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.full_name} · {item.participant_code}
                    </option>
                  ))}
              </select>
            </label>
            {error && (
              <p role="alert" className="text-sm text-red-700">
                {error}
              </p>
            )}
            <div className="action-footer">
              <button
                type="button"
                className="command"
                onClick={() => setEnrolling(false)}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="command primary"
                disabled={enrol.isPending || !participantId}
              >
                <Check className="h-4 w-4" /> Add
              </button>
            </div>
          </form>
        </Dialog>
      )}
      {editor && (
        <DemandForm
          editor={editor}
          onClose={() => setEditor(null)}
          onReview={async () => {
            setEditor(null);
            await refresh();
          }}
          onSaved={async (row) => {
            setEditor(null);
            if (!selected && typeof row.id === "string") setSelected(row.id);
            await refresh();
            if (selected)
              await client.invalidateQueries({
                queryKey: ["trainings", selected],
              });
          }}
        />
      )}
    </div>
  );
}
