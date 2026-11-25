"use client";

import { useEffect, useRef } from "react";
import { ExternalLink, FileText, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  citationIdentity,
  safeExternalUri,
  sourceForCitation,
} from "@/features/citations/utils";
import type { Citation, Source } from "@/types/api";
import { cn } from "@/lib/utils";

export function CitationDrawer({
  citations,
  sources,
  selectedIndex,
  onSelect,
  onClose,
  embedded = false,
}: {
  citations: Citation[];
  sources: Source[];
  selectedIndex: number;
  onSelect: (index: number) => void;
  onClose: () => void;
  embedded?: boolean;
}) {
  const panelRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    if (!embedded) {
      closeRef.current?.focus();
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }

      if (
        event.key !== "Tab" ||
        !window.matchMedia("(max-width: 1023px)").matches
      ) {
        return;
      }

      const focusable = panelRef.current?.querySelectorAll<HTMLElement>(
        'button:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable?.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      previous?.focus();
    };
  }, [embedded, onClose]);

  useEffect(() => {
    panelRef.current
      ?.querySelector<HTMLElement>('[data-selected="true"]')
      ?.scrollIntoView({ block: "nearest" });
  }, [selectedIndex]);

  const body = (
        <div className="min-h-0 flex-1 space-y-6 overflow-y-auto">
          {citations.length ? (
            <ol className="space-y-3" aria-label="Citations">
              {citations.map((citation, index) => {
                const selected = index === selectedIndex;
                const source = sourceForCitation(citation, sources);
                const uri = safeExternalUri(source?.uri);
                return (
                  <li key={citationIdentity(citation, index)}>
                    <article
                      data-selected={selected}
                      className={cn(
                        "rounded-md border p-4 transition-colors",
                        selected
                          ? "border-primary bg-citation/35"
                          : "border-border bg-background",
                      )}
                    >
                      <button
                        type="button"
                        className="w-full text-left outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        aria-current={selected ? "true" : undefined}
                        onClick={() => onSelect(index)}
                      >
                        <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-primary">
                          Citation {index + 1}
                        </span>
                        <span className="mt-1 block text-sm font-semibold leading-5">
                          {citation.title}
                        </span>
                      </button>
                      <dl className="mt-3 space-y-1.5 text-xs leading-5 text-muted-foreground">
                        <div className="flex gap-2">
                          <dt className="font-medium text-foreground">Source</dt>
                          <dd>{citation.source}</dd>
                        </div>
                        {citation.page !== null &&
                        citation.page !== undefined ? (
                          <div className="flex gap-2">
                            <dt className="font-medium text-foreground">Page</dt>
                            <dd>{citation.page}</dd>
                          </div>
                        ) : null}
                        {citation.reference ? (
                          <div className="flex gap-2">
                            <dt className="font-medium text-foreground">
                              Reference
                            </dt>
                            <dd>{citation.reference}</dd>
                          </div>
                        ) : null}
                      </dl>
                      {citation.snippet ? (
                        <blockquote className="mt-3 border-l-2 border-primary pl-3 font-serif text-sm leading-6 text-muted-foreground">
                          {citation.snippet}
                        </blockquote>
                      ) : null}
                      {uri ? (
                        <a
                          href={uri}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-info underline decoration-primary underline-offset-4"
                        >
                          Open source
                          <ExternalLink className="size-3" aria-hidden="true" />
                        </a>
                      ) : null}
                    </article>
                  </li>
                );
              })}
            </ol>
          ) : null}

          {sources.length ? (
            <section aria-labelledby="source-list-title">
              <h3
                id="source-list-title"
                className="text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground"
              >
                Source list
              </h3>
              <ul className="mt-3 space-y-2">
                {sources.map((source, index) => {
                  const uri = safeExternalUri(source.uri);
                  return (
                    <li
                      key={`${source.title}-${source.uri ?? source.type ?? index}`}
                      className="flex items-start gap-2 rounded-md border border-border px-3 py-2.5 text-sm"
                    >
                      <FileText
                        className="mt-0.5 size-4 shrink-0 text-primary"
                        aria-hidden="true"
                      />
                      <div className="min-w-0 flex-1">
                        <p className="font-medium">{source.title}</p>
                        {source.type ? (
                          <p className="mt-0.5 text-xs text-muted-foreground">
                            {source.type}
                          </p>
                        ) : null}
                      </div>
                      {uri ? (
                        <a
                          href={uri}
                          target="_blank"
                          rel="noopener noreferrer"
                          aria-label={`Open ${source.title}`}
                          className="rounded-sm p-1 text-info outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          <ExternalLink className="size-3.5" aria-hidden="true" />
                        </a>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            </section>
          ) : null}
        </div>
  );

  if (embedded) {
    return (
      <div
        ref={(node) => {
          panelRef.current = node;
        }}
      >
        {body}
      </div>
    );
  }

  return (
    <>
      <button
        type="button"
        aria-label="Close sources"
        className="fixed inset-0 z-[60] bg-foreground/50 md:hidden"
        onClick={onClose}
      />
      <aside
        ref={panelRef}
        role="dialog"
        aria-labelledby="citation-drawer-title"
        className="fixed inset-x-0 bottom-0 z-[70] flex h-[70vh] flex-col rounded-t-lg border-t border-border bg-surface text-foreground md:static md:z-auto md:h-full md:w-[360px] md:shrink-0 md:rounded-none md:border-l md:border-t-0"
      >
        <header className="flex shrink-0 items-center justify-between px-5 py-4">
          <h2 id="citation-drawer-title" className="font-semibold">
            Sources
          </h2>
          <Button
            ref={closeRef}
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Close sources"
            onClick={onClose}
          >
            <X className="size-4" aria-hidden="true" />
          </Button>
        </header>
        {body}
      </aside>
    </>
  );
}
