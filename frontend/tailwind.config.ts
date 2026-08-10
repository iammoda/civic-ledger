import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#101828",
        surface: "#f8f4ec",
        accent: "#0f766e",
        signal: "#c2410c",
        mist: "#dbeafe"
      },
      boxShadow: {
        card: "0 20px 45px rgba(16, 24, 40, 0.08)"
      }
    }
  },
  plugins: []
};

export default config;
