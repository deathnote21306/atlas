// packages/design-system/tailwind.preset.cjs
/** @type {import('tailwindcss').Config} */
module.exports = {
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#030712",
          900: "#0b1220",
          800: "#111827",
          700: "#1f2937",
          600: "#374151",
          500: "#6b7280",
          400: "#9ca3af",
          300: "#d1d5db",
          200: "#e5e7eb",
          100: "#f3f4f6",
        },
        positive: "#22c55e",
        warning: "#f59e0b",
        danger: "#ef4444",
        accent: "#3b82f6",
        atlas: {
          400: "#60a5fa",
          500: "#3b82f6",
          600: "#2563eb",
          700: "#1d4ed8",
        },
      },
      fontFamily: {
        sans: ["Geist", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
    },
  },
};
