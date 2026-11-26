import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center px-6 text-center">
      <h1 className="text-xl font-semibold">Page not found</h1>
      <p className="mt-2 max-w-md text-sm text-muted-foreground">
        That URL is not part of Juris AI.
      </p>
      <Link href="/app" className={`${buttonVariants()} mt-6`}>
        Workspace
      </Link>
    </div>
  );
}
