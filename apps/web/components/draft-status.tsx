"use client";

import { Check, CloudOff, LoaderCircle } from "lucide-react";

export function DraftStatus({
  busy,
  online,
  status,
}: {
  busy: boolean;
  online: boolean;
  status: string;
}) {
  return (
    <p role="status" className="flex items-center gap-2 text-sm text-muted">
      {!online ? (
        <CloudOff className="h-4 w-4" />
      ) : busy ? (
        <LoaderCircle className="h-4 w-4 animate-spin" />
      ) : status === "Saved" ? (
        <Check className="h-4 w-4" />
      ) : null}
      {status}
    </p>
  );
}
