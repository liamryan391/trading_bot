/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#13211f",
        canvas: "#f4f1ea",
        panel: "#ffffff",
        line: "#d7dfdb",
        teal: {
          750: "#0f766e",
          950: "#0d241f",
        },
        amber: {
          650: "#b45309",
        },
      },
      boxShadow: {
        panel: "0 16px 40px rgba(18, 33, 31, 0.08)",
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};

