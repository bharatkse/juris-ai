"use client";

import { useEffect, useRef } from "react";
import { ExternalLink, FileText, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  citationIdentity,
  safeExternalUri,
  sourceForCitation,
} from "@/features/citations/utils";
import type { Citation, Source } from "@/lib/api/types";
import { cn } from "@/lib/utils";

export function CitationDrawer({
  citations,
  sources,
  selectedIndex,
  onSelect,
  onClose,
}: {
  citations: Citation[];
  sources: Source[];
  selectedIndex: number;
  onSelect: (index: number) => void;
  onClose: () => void;
}) {
  const panelRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();

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
  }, [onClose]);

  useEffect(() => {
    panelRef.current
      ?.querySelector<HTMLElement>('[data-selected="true"]')
      ?.scrollIntoView({ block: "nearest" });
  }, [selectedIndex]);

  return (
    <>
      <button
        type="button"
        aria-label="Close sources"
        className="fixed inset-0 z-[60] bg-ink-950/50 lg:hidden"
        onClick={onClose}
      />
      <aside
        ref={panelRef}
        role="dialog"
        aria-labelledby="citation-drawer-title"
        className="fixed inset-x-0 bottom-0 z-[70] flex h-[70vh] flex-col rounded-t-lg border-t border-line-200 bg-paper text-ink-950 lg:static lg:z-auto lg:h-full lg:w-[360px] lg:shrink-0 lg:rounded-none lg:border-l lg:border-t-0"
      >
        <div
          className="mx-auto mt-2 h-1 w-10 rounded-full bg-line-200 lg:hidden"
          aria-hidden="true"
        />
        <header className="flex shrink-0 items-center justify-between border-b border-line-200 px-5 py-4">
          <div>
            <h2 id="citation-drawer-title" className="font-semibold">
              Sources
            </h2>
            <p className="mt-0.5 text-xs text-ink-400">
              {citations.length} citation{citations.length === 1 ? "" : "s"}
            </p>
          </div>
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

        <div className="min-h-0 flex-1 space-y-6 overflow-y-auto p-4">
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
                          ? "border-gold-600 bg-gold-100/35"
                          : "border-line-200 bg-paper-50",
                      )}
                    >
                      <button
                        type="button"
                        className="w-full text-left outline-none focus-visible:ring-2 focus-visible:ring-gold-600"
                        aria-current={selected ? "true" : undefined}
                        onClick={() => onSelect(index)}
                      >
                        <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-gold-600">
                          Citation {index + 1}
                        </span>
                        <span className="mt-1 block text-sm font-semibold leading-5">
                          {citation.title}
                        </span>
                      </button>
                      <dl className="mt-3 space-y-1.5 text-xs leading-5 text-ink-600">
                        <div className="flex gap-2">
                          <dt className="font-medium text-ink-950">Source</dt>
                          <dd>{citation.source}</dd>
                        </div>
                        {citation.page !== null &&
                        citation.page !== undefined ? (
                          <div className="flex gap-2">
                            <dt className="font-medium text-ink-950">Page</dt>
                            <dd>{citation.page}</dd>
                          </div>
                        ) : null}
                        {citation.reference ? (
                          <div className="flex gap-2">
                            <dt className="font-medium text-ink-950">
                              Reference
                            </dt>
                            <dd>{citation.reference}</dd>
                          </div>
                        ) : null}
                      </dl>
                      {citation.snippet ? (
                        <blockquote className="mt-3 border-l-2 border-gold-600 pl-3 font-serif text-sm leading-6 text-ink-600">
                          {citation.snippet}
                        </blockquote>
                      ) : null}
                      {uri ? (
                        <a
                          href={uri}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-info-600 underline decoration-gold-600 underline-offset-4"
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
                className="text-xs font-semibold uppercase tracking-[0.08em] text-ink-400"
              >
                Source list
              </h3>
              <ul className="mt-3 space-y-2">
                {sources.map((source, index) => {
                  const uri = safeExternalUri(source.uri);
                  return (
                    <li
                      key={`${source.title}-${source.uri ?? source.type ?? index}`}
                      className="flex items-start gap-2 rounded-md border border-line-200 px-3 py-2.5 text-sm"
                    >
                      <FileText
                        className="mt-0.5 size-4 shrink-0 text-gold-600"
                        aria-hidden="true"
                      />
                      <div className="min-w-0 flex-1">
                        <p className="font-medium">{source.title}</p>
                        {source.type ? (
                          <p className="mt-0.5 text-xs text-ink-400">
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
                          className="rounded-sm p-1 text-info-600 outline-none focus-visible:ring-2 focus-visible:ring-gold-600"
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
      </aside>
    </>
  );
}
