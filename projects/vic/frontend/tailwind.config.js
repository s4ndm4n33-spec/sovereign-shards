/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#070B14",
          900: "#0B1020",
          800: "#111827",
          700: "#1F2937",
          600: "#374151",
          500: "#4B5563",
          300: "#9CA3AF",
          100: "#D1D5DB",
        },
        vic: {
          glow: "#22D3EE",
          accent: "#14B8A6",
          warn: "#F59E0B",
          err: "#EF4444",
        },
      },
      fontFamily: {
        sans: ['"Inter"', "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "SFMono-Regular", "monospace"],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(34,211,238,0.25), 0 8px 30px -8px rgba(34,211,238,0.35)",
      },
    },
  },
  plugins: [],
};
