import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#0F1C2E",
          800: "#1A2B44",
          600: "#3D4F66",
          400: "#7A8BA1",
        },
        paper: {
          50: "#F7F4EE",
          DEFAULT: "#FFFCF7",
        },
        line: {
          200: "#E4DDD0",
        },
        gold: {
          600: "#B8860B",
          100: "#F4E8C4",
        },
        danger: {
          600: "#9B2C2C",
          50: "#FDECEC",
        },
        success: {
          600: "#276749",
          50: "#E6F4EA",
        },
        info: {
          600: "#2B4C7E",
          50: "#EAF0F8",
        },
      },
      fontFamily: {
        sans: [
          "var(--font-sans)",
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "\"Segoe UI\"",
          "sans-serif",
        ],
        serif: [
          "var(--font-serif)",
          "\"Source Serif 4\"",
          "Georgia",
          "Cambria",
          "serif",
        ],
      },
      borderRadius: {
        sm: "6px",
        md: "10px",
        lg: "16px",
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
