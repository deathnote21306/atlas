import type { Config } from "tailwindcss";
import preset from "@atlas/design-system/tailwind-preset";

export default {
  presets: [preset],
  content: [
    "./index.html",
    "./src/**/*.{ts,tsx}",
    "../../packages/design-system/src/**/*.{ts,tsx}",
  ],
} satisfies Config;
