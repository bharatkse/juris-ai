import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";

export default function WorkspaceNotFound() {
  return (
    <div className="flex min-h-full flex-col items-center justify-center px-6 py-16 text-center">
      <h1 className="text-xl font-semibold">Not found</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        This workspace page does not exist.
      </p>
      <Link href="/app" className={`${buttonVariants({ variant: "outline" })} mt-6`}>
        Back to workspace
      </Link>
    </div>
  );
}
