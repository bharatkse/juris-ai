export interface PinItem {
  type: "conversation" | "project";
  id: string;
}

export function movePin(
  items: readonly PinItem[],
  from: number,
  to: number,
): PinItem[] {
  if (
    from < 0 ||
    to < 0 ||
    from >= items.length ||
    to >= items.length ||
    from === to
  ) {
    return [...items];
  }
  const next = [...items];
  const [entry] = next.splice(from, 1);
  next.splice(to, 0, entry);
  return next;
}

export function togglePin(
  items: readonly PinItem[],
  target: PinItem,
): PinItem[] {
  const index = items.findIndex(
    (item) => item.type === target.type && item.id === target.id,
  );
  if (index >= 0) {
    return items.filter((_, current) => current !== index);
  }
  return [target, ...items];
}

export function isPinned(
  items: readonly PinItem[],
  target: PinItem,
): boolean {
  return items.some(
    (item) => item.type === target.type && item.id === target.id,
  );
}
