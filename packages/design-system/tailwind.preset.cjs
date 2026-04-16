// packages/design-system/tailwind.preset.cjs
/** @type {import('tailwindcss').Config} */
module.exports = {
  theme: {
    extend: {
      colors: {
        // Institutional neutrals
        ink: {
          900: "#0b1220",
          700: "#1f2a44",
          500: "#475569",
          300: "#94a3b8",
          100: "#e2e8f0",
        },
        // Semantic
        positive: "#166534",
        warning: "#b45309",
        danger: "#b91c1c",
        accent: "#1d4ed8",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
    },
  },
};
