import "dotenv/config";
import { z } from "zod";

const envSchema = z.object({
  NODE_ENV: z
    .enum(["development", "test", "production"])
    .default("development"),

  PORT: z.coerce
    .number()
    .int()
    .positive()
    .default(3000),

  HOST: z
    .string()
    .default("0.0.0.0"),

  LOG_LEVEL: z
    .enum([
      "fatal",
      "error",
      "warn",
      "info",
      "debug",
      "trace",
      "silent",
    ])
    .default("info"),

  DATABASE_URL: z
    .string()
    .min(1),

  DB_SSL: z
    .string()
    .default("true"),

  DB_POOL_MAX: z.coerce
    .number()
    .int()
    .positive()
    .default(20),

  DB_IDLE_TIMEOUT_MS: z.coerce
    .number()
    .int()
    .positive()
    .default(30000),

  DB_CONNECTION_TIMEOUT_MS: z.coerce
    .number()
    .int()
    .positive()
    .default(5000),

  BETTER_AUTH_ISSUER: z.string().optional().default("http://localhost:3000"),
  BETTER_AUTH_AUDIENCE: z.string().optional().default("truthchain-api"),
  BETTER_AUTH_JWKS_URL: z.string().optional().default("http://localhost:3000/api/auth/jwks"),

  REDIS_URL: z.string().optional().default("redis://localhost:6379"),
  AI_SERVICE_URL: z.string().optional().default("http://localhost:8000"),

  BLOCKCHAIN_RPC_URL: z.string().optional().default("https://ethereum-sepolia-rpc.publicnode.com"),
  BLOCKCHAIN_CONTRACT_ADDRESS: z.string().optional().default("0x624528e80FBE781bDDe8A91EA2A8C8c3DD5abB3B"),
  BLOCKCHAIN_PRIVATE_KEY: z.string().optional(),
});

export const env = envSchema.parse(process.env);