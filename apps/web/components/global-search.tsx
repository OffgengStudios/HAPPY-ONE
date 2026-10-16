"use client";

import {
  ArrowLeft,
  ArrowRight,
  LoaderCircle,
  RefreshCw,
  Search,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, Me } from "@/lib/api";
import {
  searchGroups,
  SearchEntity,
  SearchItem,
  SearchPage,
  SearchResult,
} from "@/lib/search";
import { Dialog } from "./dialog";

export function GlobalSearch({
  user,
  onOpen,
}: {
  user: Me;
  onOpen: (item: SearchItem) => void;
}) {
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const wasOpen = useRef(false);
  const restore = useRef(true);
  useEffect(() => {
    if (wasOpen.current && !open && restore.current)
      trigger.current?.focus({ preventScroll: true });
    wasOpen.current = open;
  }, [open]);
  if (
    !searchGroups.some((group) => user.permissions.includes(group.permission))
  )
    return null;
  return (
    <>
      <button
        ref={trigger}
        type="button"
        className="icon-button md:mr-auto md:h-10 md:min-w-0 md:max-w-[590px] md:flex-1 md:shrink md:justify-start md:gap-2 md:bg-background md:px-3 md:text-muted"
        title="Search"
        aria-label="Global search"
        onClick={() => {
          restore.current = true;
          setOpen(true);
        }}
      >
        <Search aria-hidden="true" className="h-4 w-4" />
        <span className="hidden min-w-0 truncate text-sm md:inline">
          Search records
        </span>
      </button>
      {open && (
        <SearchDialog
          onClose={() => setOpen(false)}
          onOpen={(item) => {
            restore.current = false;
            setOpen(false);
            onOpen(item);
          }}
        />
      )}
    </>
  );
}

function SearchDialog({
  onClose,
  onOpen,
}: {
  onClose: () => void;
  onOpen: (item: SearchItem) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const request = useRef<AbortController | null>(null);
  const [query, setQuery] = useState("");
  const [groups, setGroups] = useState<SearchResult["groups"] | null>(null);
  const [trails, setTrails] = useState<
    Partial<Record<SearchEntity, (string | null)[]>>
  >({});
  const [pending, setPending] = useState(false);
  const [paging, setPaging] = useState<SearchEntity | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const text = query.trim();

  useEffect(() => {
    setGroups(null);
    setTrails({});
    setError("");
    setPaging(null);
    setPending(false);
    if (text.length < 2) return;
    const controller = new AbortController();
    request.current = controller;
    const timer = window.setTimeout(() => {
      setPending(true);
      void api<SearchResult>(
        "/search",
        "POST",
        { q: text, limit: 5 },
        controller.signal,
      )
        .then((result) => {
          if (controller.signal.aborted) return;
          setGroups(result.groups);
          setTrails(
            Object.fromEntries(
              Object.keys(result.groups).map((key) => [key, [null]]),
            ),
          );
        })
        .catch((err) => {
          if (!controller.signal.aborted)
            setError(err instanceof Error ? err.message : "Unable to search.");
        })
        .finally(() => {
          if (!controller.signal.aborted) setPending(false);
        });
    }, 300);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [text, attempt]);

  async function page(
    entity: SearchEntity,
    cursor: string | null,
    nextTrail: (string | null)[],
  ) {
    if (paging) return;
    const controller = new AbortController();
    request.current?.abort();
    request.current = controller;
    setPaging(entity);
    setError("");
    try {
      const result = await api<SearchResult>(
        "/search",
        "POST",
        {
          q: text,
          limit: 5,
          entities: [entity],
          cursors: cursor ? { [entity]: cursor } : {},
        },
        controller.signal,
      );
      if (controller.signal.aborted) return;
      setGroups((current) => ({ ...current, [entity]: result.groups[entity] }));
      setTrails((current) => ({ ...current, [entity]: nextTrail }));
    } catch (err) {
      if (!controller.signal.aborted)
        setError(err instanceof Error ? err.message : "Unable to search.");
    } finally {
      if (!controller.signal.aborted) setPaging(null);
    }
  }
  useEffect(() => () => request.current?.abort(), []);

  return (
    <Dialog title="Search" onClose={onClose} initialFocus={input}>
      <div className="px-5 py-4">
        <label className="field-label">
          <span className="sr-only">Search records</span>
          <input
            ref={input}
            type="search"
            className="field"
            autoComplete="off"
            maxLength={200}
            value={query}
            placeholder="Search"
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                event.preventDefault();
                event.stopPropagation();
                onClose();
              }
            }}
            onChange={(event) => {
              if (event.target.value.trim() !== text) {
                request.current?.abort();
                setGroups(null);
              }
              setQuery(event.target.value);
            }}
          />
        </label>
        {pending && (
          <p
            role="status"
            className="mt-4 flex items-center gap-2 text-sm text-muted"
          >
            <LoaderCircle aria-hidden="true" className="h-4 w-4 animate-spin" />
            Searching...
          </p>
        )}
        {error && (
          <div className="mt-4 flex items-center gap-3">
            <p role="alert" className="text-sm text-red-700">
              {error}
            </p>
            <button
              className="icon-button"
              title="Retry search"
              aria-label="Retry search"
              onClick={() => setAttempt((value) => value + 1)}
            >
              <RefreshCw className="h-4 w-4" />
            </button>
          </div>
        )}
        {searchGroups
          .filter((group) => groups?.[group.type])
          .map((group) => {
            const result = groups![group.type] as SearchPage;
            const history = trails[group.type] ?? [null];
            return (
              <section
                key={group.type}
                aria-label={group.label}
                className="mt-5 border-t border-border pt-4"
              >
                <div className="mb-2 flex items-center justify-between gap-3">
                  <h4 className="text-sm font-semibold">{group.label}</h4>
                  <div className="flex items-center gap-1">
                    <button
                      className="icon-button"
                      aria-label={"Previous " + group.label.toLowerCase()}
                      title="Previous results"
                      disabled={!!paging || history.length < 2}
                      onClick={() =>
                        void page(
                          group.type,
                          history[history.length - 2],
                          history.slice(0, -1),
                        )
                      }
                    >
                      <ArrowLeft className="h-4 w-4" />
                    </button>
                    <button
                      className="icon-button"
                      aria-label={"Next " + group.label.toLowerCase()}
                      title="Next results"
                      disabled={!!paging || !result.next_cursor}
                      onClick={() =>
                        void page(group.type, result.next_cursor, [
                          ...history,
                          result.next_cursor,
                        ])
                      }
                    >
                      <ArrowRight className="h-4 w-4" />
                    </button>
                  </div>
                </div>
                {!result.items.length && (
                  <p className="py-3 text-sm text-muted">No results</p>
                )}
                {paging === group.type && (
                  <p role="status" className="text-sm text-muted">
                    Searching...
                  </p>
                )}
                {result.items.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className="flex min-h-14 w-full items-center justify-between gap-3 border-b border-border px-1 py-3 text-left hover:bg-gray-50 disabled:opacity-50"
                    disabled={!!paging}
                    onClick={() => onOpen(item)}
                  >
                    <span className="min-w-0">
                      <span className="block break-words text-sm font-medium">
                        {item.label}
                      </span>
                      <span className="mt-1 block break-words text-xs text-muted">
                        {item.code}
                        {item.context ? " | " + item.context : ""}
                      </span>
                    </span>
                    <ArrowRight
                      aria-hidden="true"
                      className="h-4 w-4 shrink-0"
                    />
                  </button>
                ))}
              </section>
            );
          })}
      </div>
    </Dialog>
  );
}
