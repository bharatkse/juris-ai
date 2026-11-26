import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { Inter, Source_Serif_4 } from "next/font/google";

import { Providers } from "@/components/providers";
import { THEME_BROWSER_COLORS } from "@/config/theme";
import { ThemeScript } from "@/features/theme/theme-script";

import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-sans",
});

const sourceSerif = Source_Serif_4({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-serif",
});

export const metadata: Metadata = {
  title: {
    default: "Juris AI — Legal research with sources",
    template: "%s | Juris AI",
  },
  description:
    "A source-led legal information workspace for research and contract review.",
};

export const viewport: Viewport = {
  colorScheme: "light dark",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: THEME_BROWSER_COLORS.light },
    { media: "(prefers-color-scheme: dark)", color: THEME_BROWSER_COLORS.dark },
  ],
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${sourceSerif.variable}`}
      suppressHydrationWarning
    >
      <head>
        <ThemeScript />
      </head>
      <body className="font-sans">
        <a className="skip-link" href="#main-content">
          Skip to content
        </a>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
