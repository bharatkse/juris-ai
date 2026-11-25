export const MESSAGE_VIRTUALIZATION_THRESHOLD = 80;

export function shouldVirtualizeMessages(count: number): boolean {
  return count >= MESSAGE_VIRTUALIZATION_THRESHOLD;
}
