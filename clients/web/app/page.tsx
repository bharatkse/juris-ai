import Link from "next/link";
import {
  ArrowRight,
  BookOpenText,
  FileSearch,
  LockKeyhole,
  Quote,
} from "lucide-react";

import { Logo } from "@/components/brand/logo";
import { LegalDisclaimer } from "@/components/legal-disclaimer";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const capabilities = [
  {
    icon: BookOpenText,
    title: "Legal research",
    description:
      "Frame a question, name the jurisdiction, and inspect the authorities behind the answer.",
  },
  {
    icon: FileSearch,
    title: "Contract review",
    description:
      "Surface important clauses, obligations, and risks without losing the document context.",
  },
  {
    icon: Quote,
    title: "Cited answers",
    description:
      "Trace important claims back to source material instead of relying on a black-box response.",
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-paper-50">
      <header className="border-b border-line-200">
        <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-5 sm:px-8">
          <Link href="/" aria-label="Juris AI home">
            <Logo />
          </Link>
          <nav className="flex items-center gap-1 sm:gap-3" aria-label="Account">
            <Link
              href="/login"
              className={cn(buttonVariants({ variant: "ghost" }), "px-3")}
            >
              Log in
            </Link>
            <Link
              href="/register"
              className={buttonVariants({ variant: "primary" })}
            >
              Get started
            </Link>
          </nav>
        </div>
      </header>

      <main id="main-content">
        <section className="mx-auto grid max-w-7xl items-center gap-12 px-5 py-20 sm:px-8 sm:py-28 lg:grid-cols-[1.08fr_0.92fr] lg:py-32">
          <div className="animate-fade-in">
            <p className="mb-5 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-gold-600">
              <span className="h-px w-8 bg-gold-600" aria-hidden="true" />
              Source-led legal information
            </p>
            <h1 className="max-w-3xl text-4xl font-medium leading-[1.08] tracking-[-0.035em] text-ink-950 sm:text-6xl">
              Legal research with sources you can open.
            </h1>
            <p className="mt-7 max-w-2xl text-lg leading-8 text-ink-600">
              Ask focused questions, review contracts, and inspect citations in
              a workspace designed for careful legal work.
            </p>
            <div className="mt-9 flex flex-col gap-3 sm:flex-row">
              <Link
                href="/register"
                className={buttonVariants({ variant: "primary", size: "lg" })}
              >
                Create your workspace
                <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
              <Link
                href="/login"
                className={buttonVariants({ variant: "outline", size: "lg" })}
              >
                Sign in
              </Link>
            </div>
            <p className="mt-5 flex items-center gap-2 text-xs text-ink-600">
              <LockKeyhole className="size-3.5 text-gold-600" aria-hidden="true" />
              Your session is kept in secure, httpOnly cookies.
            </p>
          </div>

          <div
            className="relative hidden min-h-[430px] border-l border-line-200 pl-12 lg:block"
            aria-hidden="true"
          >
            <div className="absolute left-12 top-0 w-[88%] rounded-lg border border-line-200 bg-paper p-7">
              <p className="text-xs font-semibold uppercase tracking-[0.1em] text-ink-400">
                Research question
              </p>
              <p className="mt-3 text-base font-medium leading-7 text-ink-950">
                Explain the scope of Article 21 of the Constitution of India.
              </p>
            </div>
            <div className="absolute bottom-0 right-0 w-[90%] rounded-lg border border-line-200 bg-paper p-7">
              <div className="mb-5 flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-[0.1em] text-ink-400">
                  Juris AI
                </p>
                <span className="rounded-full bg-success-50 px-2.5 py-1 text-[11px] font-medium text-success-600">
                  Sources checked
                </span>
              </div>
              <p className="font-serif text-[17px] leading-7 text-ink-800">
                Article 21 protects life and personal liberty, and its judicial
                interpretation extends beyond mere physical existence…
              </p>
              <div className="mt-6 flex flex-wrap gap-2">
                <span className="rounded-full border border-gold-600/40 bg-gold-100 px-3 py-1.5 text-xs text-ink-800">
                  [1] Constitution of India
                </span>
                <span className="rounded-full border border-gold-600/40 bg-gold-100 px-3 py-1.5 text-xs text-ink-800">
                  [2] Maneka Gandhi
                </span>
              </div>
            </div>
          </div>
        </section>

        <section className="border-y border-line-200 bg-paper">
          <div className="mx-auto grid max-w-7xl divide-y divide-line-200 px-5 sm:px-8 lg:grid-cols-3 lg:divide-x lg:divide-y-0">
            {capabilities.map(({ icon: Icon, title, description }) => (
              <article className="py-10 lg:px-9 lg:py-14 first:lg:pl-0" key={title}>
                <Icon className="size-5 text-gold-600" aria-hidden="true" />
                <h2 className="mt-5 text-base font-semibold">{title}</h2>
                <p className="mt-2 max-w-sm text-sm leading-6 text-ink-600">
                  {description}
                </p>
              </article>
            ))}
          </div>
        </section>
      </main>

      <footer className="mx-auto flex max-w-7xl flex-col gap-5 px-5 py-8 sm:px-8 md:flex-row md:items-center md:justify-between">
        <Logo compact />
        <LegalDisclaimer className="max-w-2xl md:text-right" />
      </footer>
    </div>
  );
}
