export function DeviceHint({
  persistence,
}: {
  persistence: "http" | "local";
}) {
  if (persistence !== "local") return null;
  return (
    <p className="text-[11px] text-muted-foreground">Saved on this device</p>
  );
}
