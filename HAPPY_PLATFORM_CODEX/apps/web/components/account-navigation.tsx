"use client";

import { Ellipsis, type LucideIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Dialog } from "./dialog";

type NavigationItem = { id: string; name: string; icon: LucideIcon };

export function AccountNavigation({
  items,
  active,
  workspace,
  onNavigate,
}: {
  items: NavigationItem[];
  active: string;
  workspace: string;
  onNavigate: (id: string) => void;
}) {
  const [more, setMore] = useState(false);
  const navigation = useRef<HTMLElement>(null);
  const moreButton = useRef<HTMLButtonElement>(null);
  const wasOpen = useRef(false);
  const preferred =
    workspace === "MANAGEMENT"
      ? ["work", "performance", "reports"]
      : workspace === "DEMAND"
        ? ["work", "dashboard", "employers"]
        : workspace === "SUPPLY"
          ? ["work", "dashboard", "participants"]
          : ["work", "vacancies", "participants"];
  const primary = new Set(
    preferred.filter((id) => items.some((item) => item.id === id)),
  );
  const overflow = items.filter((item) => !primary.has(item.id));
  const overflowActive = overflow.some((item) => item.id === active);

  useEffect(() => {
    const desktop = window.matchMedia("(min-width: 768px)");
    const close = () => {
      if (desktop.matches) setMore(false);
    };
    desktop.addEventListener("change", close);
    return () => desktop.removeEventListener("change", close);
  }, []);

  useEffect(() => {
    if (wasOpen.current && !more) {
      const target = window.matchMedia("(min-width: 768px)").matches
        ? navigation.current?.querySelector<HTMLButtonElement>(
            'button[aria-current="page"]',
          )
        : moreButton.current;
      target?.focus({ preventScroll: true });
    }
    wasOpen.current = more;
  }, [more]);

  function navigate(id: string) {
    setMore(false);
    onNavigate(id);
  }

  return (
    <>
      <nav
        ref={navigation}
        aria-label="Account navigation"
        style={{
          gridTemplateColumns: `repeat(${primary.size + 1}, minmax(0, 1fr))`,
        }}
        className="fixed inset-x-0 bottom-0 z-20 grid gap-1 border-t border-border bg-white px-2 pt-2 pb-[calc(8px+env(safe-area-inset-bottom))] md:static md:flex md:flex-col md:border-0 md:p-0"
      >
        {items.map((item) => (
          <button
            key={item.id}
            aria-label={item.name}
            title={item.name}
            aria-current={active === item.id ? "page" : undefined}
            onClick={() => navigate(item.id)}
            className={
              "nav-item min-w-0 md:flex md:flex-row md:justify-start md:px-3 md:text-sm " +
              (primary.has(item.id)
                ? "min-h-14 flex-col justify-center gap-1 px-1 text-center text-xs md:min-h-10 md:gap-2 "
                : "hidden ") +
              (active === item.id ? "active" : "")
            }
          >
            <item.icon
              aria-hidden="true"
              className="h-5 w-5 shrink-0 md:h-4 md:w-4"
            />
            <span className="min-w-0 break-words">
              {item.id === "work" && workspace === "MANAGEMENT" ? (
                <>
                  <span className="md:hidden">Attention</span>
                  <span className="hidden md:inline">{item.name}</span>
                </>
              ) : (
                item.name
              )}
            </span>
          </button>
        ))}
        <button
          ref={moreButton}
          type="button"
          className={
            "nav-item min-h-14 min-w-0 flex-col justify-center gap-1 px-1 text-center text-xs md:hidden " +
            (overflowActive ? "active" : "")
          }
          aria-haspopup="dialog"
          aria-expanded={more}
          onClick={() => setMore(true)}
        >
          <Ellipsis aria-hidden="true" className="h-5 w-5" />
          <span>More</span>
        </button>
      </nav>
      {more && (
        <Dialog title="More" placement="sheet" onClose={() => setMore(false)}>
          <nav
            aria-label="More navigation"
            className="flex flex-col gap-1 px-4 py-3 pb-[calc(12px+env(safe-area-inset-bottom))]"
          >
            {overflow.map((item) => (
              <button
                key={item.id}
                aria-current={active === item.id ? "page" : undefined}
                onClick={() => navigate(item.id)}
                className={
                  "nav-item min-h-12 " + (active === item.id ? "active" : "")
                }
              >
                <item.icon aria-hidden="true" className="h-5 w-5 shrink-0" />
                <span className="min-w-0 break-words">{item.name}</span>
              </button>
            ))}
          </nav>
        </Dialog>
      )}
    </>
  );
}
