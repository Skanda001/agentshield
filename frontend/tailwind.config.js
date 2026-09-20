/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0a0c11",
        "bg-elevated": "#0f1219",
        panel: "#14171f",
        "panel-hover": "#1a1e28",
        border: "#252a37",
        "border-strong": "#323847",
        accent: "#4b8bff",
        "accent-soft": "#4b8bff20",
        danger: "#ff4b4b",
        "danger-soft": "#ff4b4b20",
        success: "#2ecc71",
        "success-soft": "#2ecc7120",
        warn: "#ffb84b",
        "warn-soft": "#ffb84b20",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SF Mono", "Menlo", "monospace"],
      },
      boxShadow: {
        glow: "0 0 24px rgba(75, 139, 255, 0.15)",
        "glow-danger": "0 0 24px rgba(255, 75, 75, 0.15)",
        card: "0 1px 3px rgba(0, 0, 0, 0.4), 0 8px 32px rgba(0, 0, 0, 0.2)",
      },
      animation: {
        "fade-in": "fade-in 0.3s ease-out",
        "slide-up": "slide-up 0.4s cubic-bezier(0.16, 1, 0.3, 1)",
        "pulse-soft": "pulse-soft 2s ease-in-out infinite",
      },
      keyframes: {
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "slide-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-soft": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.5" },
        },
      },
    },
  },
  plugins: [],
};