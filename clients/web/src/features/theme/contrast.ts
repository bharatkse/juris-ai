import {
  TOKEN_NAMES,
  palettes,
  type NamedPalette,
  type TokenName,
  type TokenPalette,
} from "@/config/theme";

export const TEXT_CONTRAST_MIN = 4.5;
export const UI_CONTRAST_MIN = 3;

export const CONTRAST_PAIRS: Array<{
  fg: TokenName;
  bg: TokenName;
  min: number;
  usage: string;
}> = [
  { fg: "foreground", bg: "background", min: TEXT_CONTRAST_MIN, usage: "body" },
  { fg: "foreground", bg: "surface", min: TEXT_CONTRAST_MIN, usage: "cards" },
  {
    fg: "muted-foreground",
    bg: "background",
    min: TEXT_CONTRAST_MIN,
    usage: "secondary text",
  },
  {
    fg: "primary-foreground",
    bg: "primary",
    min: TEXT_CONTRAST_MIN,
    usage: "primary / gold buttons",
  },
  {
    fg: "danger-foreground",
    bg: "danger",
    min: TEXT_CONTRAST_MIN,
    usage: "destructive buttons",
  },
  {
    fg: "success-foreground",
    bg: "success",
    min: TEXT_CONTRAST_MIN,
    usage: "success chips",
  },
  {
    fg: "chat-user-foreground",
    bg: "chat-user",
    min: TEXT_CONTRAST_MIN,
    usage: "user bubbles",
  },
  {
    fg: "chat-assistant-foreground",
    bg: "chat-assistant",
    min: TEXT_CONTRAST_MIN,
    usage: "assistant bubbles",
  },
  {
    fg: "code-foreground",
    bg: "code",
    min: TEXT_CONTRAST_MIN,
    usage: "code blocks",
  },
  {
    fg: "citation-foreground",
    bg: "citation",
    min: TEXT_CONTRAST_MIN,
    usage: "citation chips",
  },
  {
    fg: "sidebar-foreground",
    bg: "sidebar",
    min: TEXT_CONTRAST_MIN,
    usage: "sidebar",
  },
  {
    fg: "sidebar-muted",
    bg: "sidebar",
    min: TEXT_CONTRAST_MIN,
    usage: "sidebar secondary",
  },
  { fg: "ring", bg: "background", min: UI_CONTRAST_MIN, usage: "focus ring" },
];

function hueToRgb(p: number, q: number, t: number): number {
  let h = t;
  if (h < 0) h += 1;
  if (h > 1) h -= 1;
  if (h < 1 / 6) return p + (q - p) * 6 * h;
  if (h < 1 / 2) return q;
  if (h < 2 / 3) return p + (q - p) * (2 / 3 - h) * 6;
  return p;
}

export function hslChannelsToRgb(
  channels: string,
): [number, number, number] {
  const match = channels.trim().match(/^([\d.]+)\s+([\d.]+)%\s+([\d.]+)%$/u);
  if (!match) {
    throw new Error(`Invalid HSL channels: ${channels}`);
  }
  const h = Number(match[1]) / 360;
  const s = Number(match[2]) / 100;
  const l = Number(match[3]) / 100;
  if (s === 0) {
    const v = Math.round(l * 255);
    return [v, v, v];
  }
  const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
  const p = 2 * l - q;
  return [
    Math.round(hueToRgb(p, q, h + 1 / 3) * 255),
    Math.round(hueToRgb(p, q, h) * 255),
    Math.round(hueToRgb(p, q, h - 1 / 3) * 255),
  ];
}

function channelLuminance(value: number): number {
  const c = value / 255;
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

export function relativeLuminance(channels: string): number {
  const [r, g, b] = hslChannelsToRgb(channels);
  return (
    0.2126 * channelLuminance(r) +
    0.7152 * channelLuminance(g) +
    0.0722 * channelLuminance(b)
  );
}

export function contrastRatio(foreground: string, background: string): number {
  const l1 = relativeLuminance(foreground);
  const l2 = relativeLuminance(background);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

export type ContrastViolation = {
  theme: string;
  fg: TokenName;
  bg: TokenName;
  usage: string;
  ratio: number;
  min: number;
};

export function auditPaletteContrast(
  theme: string,
  tokens: TokenPalette,
  pairs = CONTRAST_PAIRS,
): ContrastViolation[] {
  return pairs
    .map((pair) => {
      const ratio = contrastRatio(tokens[pair.fg], tokens[pair.bg]);
      return {
        theme,
        fg: pair.fg,
        bg: pair.bg,
        usage: pair.usage,
        ratio,
        min: pair.min,
      };
    })
    .filter((row) => row.ratio < row.min);
}

export function auditAllPalettes(
  all: Record<string, NamedPalette> = palettes,
): ContrastViolation[] {
  return Object.entries(all).flatMap(([name, palette]) =>
    auditPaletteContrast(name, palette.tokens),
  );
}

export function assertCompletePalette(tokens: TokenPalette): void {
  for (const name of TOKEN_NAMES) {
    if (!tokens[name]) {
      throw new Error(`Missing token ${name}`);
    }
  }
}
