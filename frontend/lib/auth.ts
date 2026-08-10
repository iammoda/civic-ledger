import { betterAuth } from "better-auth";
import { Pool } from "pg";

export const auth = betterAuth({
  database: new Pool({
    connectionString:
      process.env.PG_DATABASE_URL ?? "postgres://postgres:postgres@localhost:5432/civic_platform"
  }),
  secret:
    process.env.BETTER_AUTH_SECRET ??
    (process.env.NODE_ENV === "production" ? undefined : "dev-secret-do-not-use-in-production"),
  baseURL: process.env.BETTER_AUTH_URL ?? "http://localhost:3000",
  socialProviders: {
    google: {
      clientId: process.env.GOOGLE_CLIENT_ID ?? "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET ?? ""
    }
  }
});
