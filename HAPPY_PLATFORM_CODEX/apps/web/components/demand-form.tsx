"use client";

import { FormEvent, useState } from "react";
import { LoaderCircle, RefreshCw, Save } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { Field } from "@/lib/demand";
import { Dialog } from "./dialog";
import { useDraftSave } from "@/lib/use-draft-save";
import { DraftStatus } from "./draft-status";

export type Editor = {
  title: string;
  path: string;
  method?: string;
  fields: Field[];
  initial?: Record<string, unknown>;
  extra?: Record<string, unknown>;
  autosave?: boolean;
};
export function DemandForm({
  editor,
  onClose,
  onSaved,
  onReview,
  onDraftSaved,
}: {
  editor: Editor;
  onClose: () => void;
  onSaved: (row: Record<string, unknown>) => Promise<void>;
  onReview: () => Promise<void>;
  onDraftSaved?: (row: Record<string, unknown>) => Promise<void>;
}) {
  const [values, setValues] = useState<Record<string, unknown>>(() =>
    Object.fromEntries(
      editor.fields.map((field) => {
        const value = editor.initial?.[field.key];
        return [
          field.key,
          field.type === "json"
            ? JSON.stringify(value ?? true)
            : field.type === "datetime-local" && typeof value === "string"
              ? value.slice(0, 16)
              : (value ?? (field.type === "checkbox" ? false : "")),
        ];
      }),
    ),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [conflict, setConflict] = useState(false);
  function body() {
    const result: Record<string, unknown> = { ...editor.extra };
    for (const field of editor.fields) {
      const value = values[field.key];
      result[field.key] =
        field.type === "checkbox"
          ? Boolean(value)
          : value === ""
            ? null
            : field.type === "number"
              ? Number(value)
              : field.type === "json"
                ? JSON.parse(String(value))
                : field.type === "datetime-local"
                  ? String(value) + ":00Z"
                  : field.key === "accommodation_available"
                    ? value === "true"
                    : value;
    }
    return result;
  }
  const draft = useDraftSave({
    enabled: editor.autosave,
    path: editor.path,
    data: editor.autosave ? body() : {},
    version: Number(editor.extra?.version ?? 0),
    onSaved: onDraftSaved ?? (async () => {}),
  });
  const saving = busy || draft.busy;
  const close = () => {
    if (busy) return;
    if (editor.autosave) draft.close(onClose);
    else onClose();
  };
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (editor.autosave) {
      if (await draft.save(true)) onClose();
      return;
    }
    setBusy(true);
    setError("");
    setConflict(false);
    try {
      const row = await api<Record<string, unknown>>(
        editor.path,
        editor.method ?? "POST",
        body(),
      );
      await onSaved(row);
    } catch (err) {
      setConflict(
        err instanceof ApiError && err.code === "RECORD_VERSION_CONFLICT",
      );
      setError(
        err instanceof SyntaxError
          ? "Enter a valid JSON value."
          : err instanceof Error
            ? err.message
            : "Unable to save.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog title={editor.title} placement="action" onClose={close}>
      <form ref={draft.form} className="space-y-5 p-5" onSubmit={submit}>
        {editor.autosave && <DraftStatus {...draft} />}
        <div className="grid gap-4 sm:grid-cols-2">
          {editor.fields.map((field) => (
            <label
              key={field.key}
              className={
                "field-label min-w-0 " +
                (["textarea", "json"].includes(field.type ?? "")
                  ? "sm:col-span-2"
                  : "")
              }
            >
              {field.type === "checkbox" ? (
                <span className="flex min-h-10 items-center gap-2">
                  <input
                    type="checkbox"
                    checked={Boolean(values[field.key])}
                    disabled={busy}
                    onChange={(event) =>
                      setValues({
                        ...values,
                        [field.key]: event.target.checked,
                      })
                    }
                  />
                  {field.label}
                </span>
              ) : (
                <>
                  {field.label}
                  {field.type === "select" ? (
                    <select
                      className="field"
                      required={field.required}
                      disabled={busy}
                      value={String(values[field.key] ?? "")}
                      onChange={(event) =>
                        setValues({
                          ...values,
                          [field.key]: event.target.value,
                        })
                      }
                    >
                      <option value="">Not assigned</option>
                      {field.options?.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  ) : field.type === "textarea" || field.type === "json" ? (
                    <textarea
                      className="field min-h-24"
                      required={field.required}
                      disabled={busy}
                      maxLength={field.max}
                      value={String(values[field.key] ?? "")}
                      onChange={(event) =>
                        setValues({
                          ...values,
                          [field.key]: event.target.value,
                        })
                      }
                    />
                  ) : (
                    <input
                      className="field"
                      type={field.type ?? "text"}
                      required={field.required}
                      disabled={busy}
                      min={field.type === "number" ? field.min : undefined}
                      max={field.type === "number" ? field.max : undefined}
                      maxLength={
                        field.type === "number" ? undefined : field.max
                      }
                      step={field.step}
                      value={String(values[field.key] ?? "")}
                      onChange={(event) =>
                        setValues({
                          ...values,
                          [field.key]: event.target.value,
                        })
                      }
                    />
                  )}
                </>
              )}
            </label>
          ))}
        </div>
        {(error || draft.error) && (
          <p role="alert" className="text-sm text-red-700">
            {error || draft.error}
          </p>
        )}
        {(conflict || draft.conflict) && (
          <button
            className="command"
            type="button"
            disabled={saving}
            onClick={() => void onReview()}
          >
            <RefreshCw className="h-4 w-4" />
            Review latest record
          </button>
        )}
        <div className="action-footer">
          <button
            type="button"
            className="command"
            disabled={saving}
            onClick={close}
          >
            {editor.autosave ? "Done" : "Cancel"}
          </button>
          <button
            type="submit"
            className="command primary"
            disabled={
              saving || (editor.autosave && (!draft.online || draft.conflict))
            }
          >
            {saving ? (
              <LoaderCircle className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            {editor.autosave ? "Save draft" : "Save"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
