/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{vue,js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef6ff",
          100: "#d9eaff",
          200: "#bcd9ff",
          300: "#8ec1ff",
          400: "#599dff",
          500: "#3479fb",
          600: "#1f5bf0",
          700: "#1746dc",
          800: "#193bb2",
          900: "#1a388c",
          950: "#152454"
        }
      },
      fontFamily: {
        sans: ["'Segoe UI'", "system-ui", "-apple-system", "Roboto", "sans-serif"]
      },
      boxShadow: {
        card: "0 10px 30px -12px rgba(20, 40, 90, 0.25)"
      }
    }
  },
  plugins: []
}