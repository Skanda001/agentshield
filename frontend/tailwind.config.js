/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0b0d12",
        panel: "#14171f",
        border: "#262b38",
        accent: "#4b8bff",
        danger: "#ff4b4b",
        success: "#2ecc71",
        warn: "#ffb84b",
      },
    },
  },
  plugins: [],
};