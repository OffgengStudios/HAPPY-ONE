"use client";

import { FormEvent, useState } from "react";
import { Plus, Save, Trash2, RefreshCw } from "lucide-react";
import { useDraftSave } from "@/lib/use-draft-save";
import { Field } from "@/lib/demand";
import {
  educationFields,
  employmentFields,
  experienceFields,
  skillFields,
} from "@/lib/supply";
import { Dialog } from "./dialog";
import { DraftStatus } from "./draft-status";

type Values = Record<string, unknown>;
function normalize(fields: Field[], values: Values): Values {
  return Object.fromEntries(
    fields.map((field) => [
      field.key,
      field.type === "checkbox"
        ? Boolean(values[field.key])
        : values[field.key] === "" || values[field.key] == null
          ? null
          : field.type === "number"
            ? Number(values[field.key])
            : values[field.key],
    ]),
  );
}
function Controls({
  fields,
  values,
  onChange,
  disabled,
}: {
  fields: Field[];
  values: Values;
  onChange: (values: Values) => void;
  disabled: boolean;
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {fields.map((field) => (
        <label key={field.key} className="field-label min-w-0">
          {field.type === "checkbox" ? (
            <span className="flex min-h-10 items-center gap-2">
              <input
                type="checkbox"
                disabled={disabled}
                checked={Boolean(values[field.key])}
                onChange={(event) =>
                  onChange({ ...values, [field.key]: event.target.checked })
                }
              />
              {field.label}
            </span>
          ) : (
            <>
              {field.label}
              {field.type === "textarea" ? (
                <textarea
                  className="field min-h-24"
                  disabled={disabled}
                  required={field.required}
                  maxLength={field.max}
                  value={String(values[field.key] ?? "")}
                  onChange={(event) =>
                    onChange({ ...values, [field.key]: event.target.value })
                  }
                />
              ) : (
                <input
                  className="field"
                  type={field.type ?? "text"}
                  disabled={disabled}
                  required={field.required}
                  min={field.min}
                  max={field.type === "number" ? field.max : undefined}
                  maxLength={field.type !== "number" ? field.max : undefined}
                  value={String(values[field.key] ?? "")}
                  onChange={(event) =>
                    onChange({ ...values, [field.key]: event.target.value })
                  }
                />
              )}
            </>
          )}
        </label>
      ))}
    </div>
  );
}
export function SupplyCollections({
  section,
  participant,
  onClose,
  onSaved,
}: {
  section: "education" | "employment";
  participant: Values & { id: string; version: number };
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const groups =
    section === "education"
      ? [
          {
            key: "items",
            title: "Qualification",
            fields: educationFields,
            initial: "education",
            max: 30,
          },
        ]
      : [
          {
            key: "experience",
            title: "Experience",
            fields: experienceFields,
            initial: "experience",
            max: 30,
          },
          {
            key: "skills",
            title: "Skill",
            fields: skillFields,
            initial: "skills",
            max: 100,
          },
        ];
  const [values, setValues] = useState<Values>(participant);
  const [collections, setCollections] = useState<Record<string, Values[]>>(() =>
    Object.fromEntries(
      groups.map((group) => [
        group.key,
        ((participant[group.initial] as Values[]) ?? []).map((item) =>
          normalize(group.fields, item),
        ),
      ]),
    ),
  );
  const body: Values =
    section === "employment" ? normalize(employmentFields, values) : {};
  groups.forEach((group) => {
    body[group.key] = collections[group.key].map((item) =>
      normalize(group.fields, item),
    );
  });
  const draft = useDraftSave({
    enabled: true,
    path: "/participants/" + participant.id + "/onboarding/" + section,
    data: body,
    version: participant.version,
    onSaved: async () => {
      await onSaved();
    },
  });
  const close = () => draft.close(onClose);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (await draft.save(true)) onClose();
  }
  return (
    <Dialog
      title={section === "education" ? "Edit education" : "Edit employment"}
      placement="action"
      onClose={close}
    >
      <form ref={draft.form} className="space-y-5 p-5" onSubmit={submit}>
        <DraftStatus {...draft} />
        {section === "employment" && (
          <Controls
            fields={employmentFields}
            values={values}
            onChange={setValues}
            disabled={false}
          />
        )}
        {groups.map((group) => (
          <section
            key={group.key}
            className="space-y-4 border-t border-border pt-4"
          >
            <div className="flex items-center justify-between gap-3">
              <h4 className="text-sm font-semibold">{group.title}</h4>
              <button
                className="command"
                type="button"
                disabled={collections[group.key].length >= group.max}
                onClick={() =>
                  setCollections({
                    ...collections,
                    [group.key]: [...collections[group.key], {}],
                  })
                }
              >
                <Plus className="h-4 w-4" />
                Add {group.title.toLowerCase()}
              </button>
            </div>
            {collections[group.key].map((item, index) => (
              <fieldset
                key={index}
                className="space-y-3 border-b border-border pb-4"
              >
                <legend className="mb-3 text-xs text-muted">
                  {group.title} {index + 1}
                </legend>
                <Controls
                  fields={group.fields}
                  values={item}
                  disabled={false}
                  onChange={(next) =>
                    setCollections({
                      ...collections,
                      [group.key]: collections[group.key].map((old, i) =>
                        i === index ? next : old,
                      ),
                    })
                  }
                />
                <button
                  className="icon-button"
                  type="button"
                  title={"Remove " + group.title.toLowerCase()}
                  aria-label={
                    "Remove " + group.title.toLowerCase() + " " + (index + 1)
                  }
                  onClick={() =>
                    setCollections({
                      ...collections,
                      [group.key]: collections[group.key].filter(
                        (_, i) => i !== index,
                      ),
                    })
                  }
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </fieldset>
            ))}
          </section>
        ))}
        {draft.error && (
          <p role="alert" className="text-sm text-red-700">
            {draft.error}
          </p>
        )}
        {draft.conflict && (
          <button
            className="command"
            type="button"
            onClick={() => {
              void onSaved();
              onClose();
            }}
          >
            <RefreshCw className="h-4 w-4" />
            Review latest record
          </button>
        )}
        <div className="action-footer">
          <button
            className="command"
            type="button"
            disabled={draft.busy}
            onClick={close}
          >
            Done
          </button>
          <button
            className="command primary"
            disabled={draft.busy || !draft.online || draft.conflict}
          >
            <Save className="h-4 w-4" />
            Save draft
          </button>
        </div>
      </form>
    </Dialog>
  );
}
