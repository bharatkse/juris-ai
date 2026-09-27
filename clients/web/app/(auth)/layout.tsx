import Link from "next/link";
import type { ReactNode } from "react";
import { BookOpenCheck, FileLock2, Scale } from "lucide-react";

import { Logo } from "@/components/brand/logo";
import { LegalDisclaimer } from "@/components/legal-disclaimer";

const assurances = [
  { icon: BookOpenCheck, text: "Answers designed around inspectable sources" },
  { icon: FileLock2, text: "Tokens stay out of browser JavaScript" },
  { icon: Scale, text: "Built for careful, jurisdiction-aware questions" },
];

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="grid min-h-screen bg-paper-50 lg:grid-cols-[minmax(360px,0.82fr)_1.18fr]">
      <aside className="hidden flex-col justify-between bg-ink-950 p-10 text-paper lg:flex xl:p-14">
        <Link href="/" aria-label="Juris AI home">
          <Logo inverse />
        </Link>
        <div className="max-w-md">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-gold-600">
            Your legal workspace
          </p>
          <h2 className="mt-5 text-3xl font-medium leading-tight tracking-[-0.025em]">
            Research deliberately. Review the source.
          </h2>
          <p className="mt-5 text-sm leading-7 text-paper/65">
            Juris AI helps individuals structure legal questions and examine
            grounded responses without pretending to replace counsel.
          </p>
          <ul className="mt-9 space-y-4">
            {assurances.map(({ icon: Icon, text }) => (
              <li className="flex items-center gap-3 text-sm text-paper/80" key={text}>
                <span className="grid size-8 place-items-center rounded-md border border-paper/15">
                  <Icon className="size-4 text-gold-600" aria-hidden="true" />
                </span>
                {text}
              </li>
            ))}
          </ul>
        </div>
        <LegalDisclaimer inverse className="max-w-md" />
      </aside>

      <main
        id="main-content"
        className="flex min-h-screen items-center justify-center px-5 py-10 sm:px-8"
      >
        <div className="w-full max-w-[430px]">
          <Link
            href="/"
            aria-label="Juris AI home"
            className="mb-8 inline-flex lg:hidden"
          >
            <Logo />
          </Link>
          {children}
          <LegalDisclaimer className="mt-6 lg:hidden" />
        </div>
      </main>
    </div>
  );
}
