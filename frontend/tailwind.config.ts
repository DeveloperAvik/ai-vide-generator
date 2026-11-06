import type { Config } from "tailwindcss";
export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: { canvas: "rgb(var(--canvas) / <alpha-value>)", surface: "rgb(var(--surface) / <alpha-value>)", raised: "rgb(var(--raised) / <alpha-value>)", line: "rgb(var(--line) / <alpha-value>)", "on-brand": "#ffffff",
        brand: { 400: "rgb(var(--brand-400) / <alpha-value>)", 500: "rgb(var(--brand-500) / <alpha-value>)", 600: "rgb(var(--brand-600) / <alpha-value>)" },
        slate: { 50: "rgb(var(--slate-50) / <alpha-value>)", 100: "rgb(var(--slate-100) / <alpha-value>)", 200: "rgb(var(--slate-200) / <alpha-value>)", 300: "rgb(var(--slate-300) / <alpha-value>)", 400: "rgb(var(--slate-400) / <alpha-value>)", 500: "rgb(var(--slate-500) / <alpha-value>)", 600: "rgb(var(--slate-600) / <alpha-value>)", 700: "rgb(var(--slate-700) / <alpha-value>)", 800: "rgb(var(--slate-800) / <alpha-value>)", 900: "rgb(var(--slate-900) / <alpha-value>)", 950: "rgb(var(--slate-950) / <alpha-value>)" } },
      fontFamily: { sans: ["ui-sans-serif", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Inter", "Roboto", "sans-serif"], mono: ["ui-monospace", "SF Mono", "Menlo", "monospace"] },
      boxShadow: { card: "var(--shadow-card)" },
      keyframes: { shimmer: { "100%": { transform: "translateX(100%)" } }, indeterminate: { from: { transform: "translateX(-100%)" }, to: { transform: "translateX(250%)" } },
        sparkle: { "0%": { opacity: "0", transform: "translateY(0) scale(.6)" }, "40%": { opacity: ".9" }, "100%": { opacity: "0", transform: "translateY(-28px) scale(1)" } },
        sheen: { from: { backgroundPosition: "0% 0" }, to: { backgroundPosition: "200% 0" } },
        popIn: { from: { opacity: "0", transform: "scale(.7)" }, "60%": { transform: "scale(1.12)" } },
        fadeUp: { from: { opacity: "0", transform: "translateY(8px)" } },
        ring: { from: { opacity: ".8", transform: "scale(.6)" }, to: { opacity: "0", transform: "scale(2.2)" } },
        toastIn: { from: { opacity: "0", transform: "translateY(8px)" }, to: { opacity: "1", transform: "none" } } },
      animation: {
        toast: "toastIn .18s ease-out", indeterminate: "indeterminate 1.4s ease-in-out infinite", sparkle: "sparkle 3.2s ease-out infinite",
        sheen: "sheen 6s linear infinite", pop: "popIn .45s ease-out", "fade-up": "fadeUp .5s ease-out", ring: "ring .9s ease-out",
      },
    },
  },
  plugins: [],
} satisfies Config;
