import type { Config } from "tailwindcss";

const hsl = (token: string) => `hsl(var(--${token}) / <alpha-value>)`;

const config: Config = {
  darkMode: "class",
  content: [
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: hsl("background"),
        foreground: hsl("foreground"),
        surface: {
          DEFAULT: hsl("surface"),
          elevated: hsl("surface-elevated"),
        },
        hover: hsl("hover"),
        border: hsl("border"),
        muted: {
          DEFAULT: hsl("muted"),
          foreground: hsl("muted-foreground"),
        },
        primary: {
          DEFAULT: hsl("primary"),
          foreground: hsl("primary-foreground"),
        },
        accent: {
          DEFAULT: hsl("accent"),
          foreground: hsl("accent-foreground"),
        },
        ring: hsl("ring"),
        success: {
          DEFAULT: hsl("success"),
          foreground: hsl("success-foreground"),
        },
        warning: {
          DEFAULT: hsl("warning"),
          foreground: hsl("warning-foreground"),
        },
        danger: {
          DEFAULT: hsl("danger"),
          foreground: hsl("danger-foreground"),
        },
        info: {
          DEFAULT: hsl("info"),
          foreground: hsl("info-foreground"),
        },
        chat: {
          user: hsl("chat-user"),
          "user-foreground": hsl("chat-user-foreground"),
          assistant: hsl("chat-assistant"),
          "assistant-foreground": hsl("chat-assistant-foreground"),
        },
        code: {
          DEFAULT: hsl("code"),
          foreground: hsl("code-foreground"),
        },
        citation: {
          DEFAULT: hsl("citation"),
          foreground: hsl("citation-foreground"),
        },
        sidebar: {
          DEFAULT: hsl("sidebar"),
          foreground: hsl("sidebar-foreground"),
          muted: hsl("sidebar-muted"),
          border: hsl("sidebar-border"),
        },
        selection: hsl("selection"),
        skeleton: hsl("skeleton"),
      },
      fontFamily: {
        sans: [
          "var(--font-sans)",
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          '"Segoe UI"',
          "sans-serif",
        ],
        serif: [
          "var(--font-serif)",
          '"Source Serif 4"',
          "Georgia",
          "Cambria",
          "serif",
        ],
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        xl: "var(--radius-xl)",
      },
      maxWidth: {
        chat: "var(--chat-column)",
      },
      transitionDuration: {
        fast: "150ms",
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "200% 0" },
          "100%": { backgroundPosition: "-200% 0" },
        },
      },
      animation: {
        "fade-in": "fade-in 420ms ease-out both",
        shimmer: "shimmer 1.8s linear infinite",
      },
    },
  },
  plugins: [],
};

export default config;
