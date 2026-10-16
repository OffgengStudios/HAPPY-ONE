"use client";

import {
  BriefcaseBusiness,
  Building2,
  Plus,
  UserRoundPlus,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Me } from "@/lib/api";
import { Dialog } from "./dialog";

export type QuickAddKind = "participants" | "employers" | "vacancies";
const actions = [
  {
    kind: "participants" as const,
    name: "New participant",
    icon: UserRoundPlus,
    permissions: ["participant:view", "participant:create"],
  },
  {
    kind: "employers" as const,
    name: "New employer",
    icon: Building2,
    permissions: ["organization:view", "organization:create"],
  },
  {
    kind: "vacancies" as const,
    name: "New vacancy",
    icon: BriefcaseBusiness,
    permissions: ["vacancy:view", "vacancy:create", "organization:view"],
  },
];

export function QuickAdd({
  user,
  workspace,
  onCreate,
  onDesktop,
}: {
  user: Me;
  workspace: string;
  onCreate: (kind: QuickAddKind) => void;
  onDesktop: () => void;
}) {
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const wasOpen = useRef(false);
  useEffect(() => {
    if (wasOpen.current && !open) {
      if (window.matchMedia("(max-width: 767px)").matches)
        trigger.current?.focus({ preventScroll: true });
      else onDesktop();
    }
    wasOpen.current = open;
  }, [open, onDesktop]);
  useEffect(() => {
    const desktop = window.matchMedia("(min-width: 768px)");
    const resize = () => {
      if (!desktop.matches || !open) return;
      setOpen(false);
    };
    desktop.addEventListener("change", resize);
    return () => desktop.removeEventListener("change", resize);
  }, [open]);
  const priority: QuickAddKind[] =
    workspace === "DEMAND"
      ? ["employers", "vacancies", "participants"]
      : ["participants", "employers", "vacancies"];
  const choices = actions
    .filter((action) =>
      action.permissions.every((permission) =>
        user.permissions.includes(permission),
      ),
    )
    .sort(
      (left, right) =>
        priority.indexOf(left.kind) - priority.indexOf(right.kind),
    );
  if (!choices.length) return null;
  const label = choices.length === 1 ? choices[0].name : "Quick add";
  return (
    <>
      <button
        ref={trigger}
        type="button"
        className="quick-add-trigger fixed bottom-[calc(96px+env(safe-area-inset-bottom))] right-5 z-20 flex h-14 w-14 items-center justify-center rounded-full border border-primary bg-primary text-primary-foreground shadow-md hover:bg-primary-hover md:hidden"
        title={label}
        aria-label="Quick add"
        aria-haspopup="dialog"
        aria-expanded={choices.length > 1 ? open : undefined}
        onClick={() =>
          choices.length === 1 ? onCreate(choices[0].kind) : setOpen(true)
        }
      >
        <Plus aria-hidden="true" className="h-6 w-6" />
      </button>
      {open && (
        <Dialog
          title="Quick add"
          placement="sheet"
          onClose={() => setOpen(false)}
        >
          <div className="space-y-1 p-4 pb-[calc(16px+env(safe-area-inset-bottom))]">
            {choices.map((action) => (
              <button
                type="button"
                key={action.kind}
                className="nav-item min-h-12 w-full"
                onClick={() => {
                  setOpen(false);
                  onCreate(action.kind);
                }}
              >
                <action.icon aria-hidden="true" className="h-4 w-4 shrink-0" />
                {action.name}
              </button>
            ))}
          </div>
        </Dialog>
      )}
    </>
  );
}
