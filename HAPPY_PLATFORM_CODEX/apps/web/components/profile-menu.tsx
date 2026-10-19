"use client";

import { LoaderCircle, LogOut, ShieldCheck, UserRound } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { Me } from "@/lib/api";

export function ProfileMenu({
  user,
  workspace,
  onSecurity,
  onLogout,
}: {
  user: Me;
  workspace: string;
  onSecurity: () => void;
  onLogout: () => Promise<boolean>;
}) {
  const id = useId();
  const trigger = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const initials = user.full_name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => Array.from(part)[0])
    .join("")
    .toUpperCase();

  useEffect(() => {
    const dismiss = () => menu.current?.hidePopover();
    window.addEventListener("resize", dismiss);
    return () => window.removeEventListener("resize", dismiss);
  }, []);

  function position() {
    const anchor = trigger.current?.getBoundingClientRect();
    if (!menu.current || !anchor) return;
    menu.current.style.top = `${anchor.bottom + 8}px`;
    menu.current.style.right = `${Math.max(16, window.innerWidth - anchor.right)}px`;
  }
  function close() {
    menu.current?.hidePopover();
    trigger.current?.focus({ preventScroll: true });
  }
  async function logout() {
    setBusy(true);
    setError(false);
    if (!(await onLogout())) {
      setBusy(false);
      setError(true);
    }
  }

  return (
    <>
      <span
        className="ml-auto hidden max-w-48 shrink-0 text-right text-sm md:block"
        title={user.full_name}
      >
        <span className="block truncate font-semibold">{user.full_name}</span>
        <span className="block truncate text-xs text-muted">{workspace}</span>
      </span>
      <button
        ref={trigger}
        type="button"
        className="account-avatar icon-button h-10 w-10 rounded-full border-primary bg-primary text-sm font-bold text-primary-foreground hover:bg-primary-hover"
        title="Account menu"
        aria-label="Account menu"
        aria-haspopup="menu"
        aria-expanded={open}
        popoverTarget={id}
        onClick={position}
      >
        {initials ? (
          <span aria-hidden="true">{initials}</span>
        ) : (
          <UserRound aria-hidden="true" className="h-4 w-4" />
        )}
      </button>
      <div
        id={id}
        ref={menu}
        popover="auto"
        role="menu"
        aria-label="Account"
        className="fixed inset-auto m-0 max-h-[calc(100dvh-96px)] w-72 max-w-[calc(100vw-32px)] overflow-y-auto rounded-md border border-border bg-white p-0 shadow-lg"
        onToggle={(event) => {
          const shown = event.newState === "open";
          setOpen(shown);
          if (shown)
            menu.current
              ?.querySelector<HTMLButtonElement>('[role="menuitem"]')
              ?.focus();
        }}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.preventDefault();
            close();
            return;
          }
          if (event.key === "Tab") {
            menu.current?.hidePopover();
            return;
          }
          if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key))
            return;
          event.preventDefault();
          const choices = Array.from(
            menu.current?.querySelectorAll<HTMLButtonElement>(
              '[role="menuitem"]:not(:disabled)',
            ) ?? [],
          );
          if (!choices.length) return;
          const index = choices.findIndex(
            (button) => button === document.activeElement,
          );
          const next =
            event.key === "Home"
              ? 0
              : event.key === "End"
                ? choices.length - 1
                : (index +
                    (event.key === "ArrowUp" ? -1 : 1) +
                    choices.length) %
                  choices.length;
          choices[next]?.focus();
        }}
      >
        <div className="border-b border-border px-4 py-3">
          <p className="break-words text-sm font-semibold">{user.full_name}</p>
          <p className="mt-1 break-words text-xs text-muted">{user.email}</p>
          <p className="mt-2 text-xs text-primary">{workspace}</p>
        </div>
        <div className="p-2">
          <button
            type="button"
            role="menuitem"
            className="nav-item min-h-11 w-full"
            disabled={busy}
            onClick={() => {
              close();
              onSecurity();
            }}
          >
            <ShieldCheck aria-hidden="true" className="h-4 w-4 shrink-0" />
            Account security
          </button>
          <button
            type="button"
            role="menuitem"
            className="nav-item min-h-11 w-full"
            disabled={busy}
            onClick={() => void logout()}
          >
            {busy ? (
              <LoaderCircle
                aria-hidden="true"
                className="h-4 w-4 animate-spin"
              />
            ) : (
              <LogOut aria-hidden="true" className="h-4 w-4 shrink-0" />
            )}
            Sign out
          </button>
          {error && (
            <p role="alert" className="px-3 py-2 text-sm text-red-700">
              Unable to sign out. Try again.
            </p>
          )}
        </div>
      </div>
    </>
  );
}
