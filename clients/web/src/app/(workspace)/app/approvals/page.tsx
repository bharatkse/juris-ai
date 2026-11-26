export default function ApprovalsPage() {
  return (
    <div className="mx-auto h-full w-full max-w-3xl overflow-y-auto px-4 py-8 sm:px-8">
      <h1 className="text-2xl font-semibold tracking-[-0.02em]">Plans</h1>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">
        Tool approvals appear in the conversation when an agent needs
        confirmation. There is no list endpoint for pending approvals.
      </p>
    </div>
  );
}
