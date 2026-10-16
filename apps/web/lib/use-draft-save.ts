"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api";

type Options = {
  enabled?: boolean;
  path: string;
  data: Record<string, unknown>;
  version: number;
  onSaved: (row: Record<string, unknown>) => Promise<void>;
};

export function useDraftSave(options: Options) {
  const form = useRef<HTMLFormElement>(null);
  const latest = useRef(options);
  latest.current = options;
  const fingerprint = JSON.stringify(options.data);
  const [saved, setSaved] = useState(fingerprint);
  const savedRef = useRef(fingerprint);
  const version = useRef(options.version);
  const attempted = useRef("");
  const mounted = useRef(true);
  const inFlight = useRef(false);
  const conflicted = useRef(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [conflict, setConflict] = useState(false);
  const [online, setOnline] = useState(true);
  const dirty = fingerprint !== saved;

  useEffect(() => {
    mounted.current = true;
    const update = () => {
      setOnline(navigator.onLine);
      if (navigator.onLine) attempted.current = "";
    };
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      mounted.current = false;
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);

  const save = useCallback(async (force = false) => {
    const current = latest.current;
    if (!current.enabled || inFlight.current || conflicted.current)
      return false;
    if (!navigator.onLine) {
      setOnline(false);
      return false;
    }
    if (!form.current?.checkValidity()) return false;
    const snapshot = JSON.stringify(current.data);
    if (snapshot === savedRef.current && !force) return true;
    attempted.current = snapshot;
    inFlight.current = true;
    setBusy(true);
    setError("");
    try {
      const row = await api<Record<string, unknown>>(current.path, "PATCH", {
        ...current.data,
        version: version.current,
      });
      if (typeof row.version !== "number")
        throw new Error(
          "Save acknowledgement unavailable. Review latest record.",
        );
      version.current = row.version;
      savedRef.current = snapshot;
      if (mounted.current) {
        setSaved(snapshot);
        await current.onSaved(row);
      }
      return snapshot === JSON.stringify(latest.current.data);
    } catch (err) {
      if (mounted.current) {
        // Never retry a stale version or an uncertain acknowledgement as a write.
        conflicted.current =
          (err instanceof ApiError && err.code === "RECORD_VERSION_CONFLICT") ||
          (err instanceof Error &&
            err.message.startsWith("Save acknowledgement"));
        setConflict(conflicted.current);
        setError(err instanceof Error ? err.message : "Unable to save draft.");
      }
      return false;
    } finally {
      inFlight.current = false;
      if (mounted.current) setBusy(false);
    }
  }, []);

  useEffect(() => {
    if (
      !options.enabled ||
      !online ||
      !dirty ||
      busy ||
      conflict ||
      attempted.current === fingerprint
    )
      return;
    const timer = window.setTimeout(() => void save(), 900);
    return () => window.clearTimeout(timer);
  }, [options.enabled, online, dirty, busy, conflict, fingerprint, save]);

  useEffect(() => {
    if (!options.enabled || (!dirty && !busy)) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [options.enabled, dirty, busy]);

  function close(onClose: () => void) {
    if (inFlight.current) return;
    if (!dirty || window.confirm("Discard unsaved changes?")) onClose();
  }

  return {
    form,
    busy,
    dirty,
    online,
    error,
    conflict,
    save,
    close,
    status: !online
      ? "Offline - changes not saved"
      : busy
        ? "Saving..."
        : conflict
          ? "Record changed - review required"
          : error
            ? "Draft not saved"
            : dirty
              ? "Unsaved changes"
              : "Saved",
  };
}
