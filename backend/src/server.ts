import { env } from "./config/env";
import { buildApp } from "./app";

const app = buildApp();

async function start() {
  try {
    await app.listen({
      port: env.PORT,
      host: env.HOST,
    });

    app.log.info(
      `TruthChain backend running on ${env.HOST}:${env.PORT}`,
    );
  } catch (error) {
    app.log.error(error);
    process.exit(1);
  }
}

start();