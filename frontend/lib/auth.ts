import { betterAuth } from "better-auth";
import { Pool } from "pg";

// Missing secret must degrade (auth disabled-ish), never crash the site:
// better-auth throws an unhandled rejection at import time otherwise.
const secret =
  process.env.BETTER_AUTH_SECRET ??
  (process.env.NODE_ENV === "production"
    ? (console.error(
        "BETTER_AUTH_SECRET is not set — using an ephemeral secret. " +
          "Sessions will reset on every restart. Set it in .env!"
      ),
      `ephemeral-${Math.random().toString(36).slice(2)}${Date.now()}`)
    : "dev-secret-do-not-use-in-production");

export const auth = betterAuth({
  database: new Pool({
    connectionString:
      process.env.PG_DATABASE_URL ?? "postgres://postgres:postgres@localhost:5432/civic_platform"
  }),
  secret,
  baseURL: process.env.BETTER_AUTH_URL ?? "http://localhost:3000",
  socialProviders: {
    google: {
      clientId: process.env.GOOGLE_CLIENT_ID ?? "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET ?? ""
    }
  }
});
