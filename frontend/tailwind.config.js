/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'sbb-red': '#eb0000',
        'sbb-red-dark': '#c60018',
        'sbb-gray': '#444444',
        'sbb-light': '#f6f6f6',
      }
    },
  },
  plugins: [],
}
