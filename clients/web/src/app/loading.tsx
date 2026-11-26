import { Skeleton } from "@/components/ui/skeleton";

export default function RootLoading() {
  return (
    <div className="flex min-h-dvh items-center justify-center px-6">
      <Skeleton className="h-10 w-48" />
    </div>
  );
}
