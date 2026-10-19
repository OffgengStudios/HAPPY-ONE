"use client";

import { X } from "lucide-react";
import { useEffect, useRef, type RefObject } from "react";

export function Dialog({
  title,
  onClose,
  children,
  placement = "center",
  initialFocus,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  placement?: "center" | "sheet" | "action";
  initialFocus?: RefObject<HTMLElement | null>;
}) {
  const reference = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = reference.current;
    const opener = document.activeElement;
    dialog?.showModal();
    initialFocus?.current?.focus({ preventScroll: true });
    return () => {
      dialog?.close();
      if (placement !== "action") return;
      queueMicrotask(() => {
        if (document.querySelector("dialog[open]")) return;
        if (
          opener instanceof HTMLElement &&
          opener !== document.body &&
          opener !== document.documentElement &&
          opener.isConnected &&
          opener.getClientRects().length
        )
          opener.focus({ preventScroll: true });
        else
          document
            .querySelector<HTMLElement>('[aria-label="Workspace content"]')
            ?.focus({ preventScroll: true });
      });
    };
  }, [initialFocus, placement]);
  return (
    <dialog
      ref={reference}
      data-placement={placement}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      aria-label={title}
      className={
        "overflow-y-auto border border-border bg-white p-0 shadow-xl backdrop:bg-black/30 " +
        (placement === "action"
          ? "fixed inset-y-0 left-0 right-0 m-0 h-dvh max-h-dvh w-full max-w-none rounded-none md:left-auto md:max-w-xl"
          : placement === "sheet"
            ? "fixed inset-x-0 bottom-0 top-auto m-0 max-h-[80dvh] w-full max-w-none rounded-t-lg"
            : "m-auto max-h-[90dvh] w-[calc(100%-32px)] max-w-xl rounded-md")
      }
    >
      <div
        className={
          "flex items-center justify-between gap-3 border-b border-border bg-white px-5 py-4 " +
          (placement === "action" ? "sticky top-0 z-10" : "")
        }
      >
        <h3 className="text-lg font-semibold">{title}</h3>
        <button
          type="button"
          className="icon-button"
          onClick={onClose}
          title="Close"
          aria-label="Close"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
      {children}
    </dialog>
  );
}
