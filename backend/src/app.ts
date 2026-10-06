import Fastify from "fastify";
import { env } from "./config/env";
import cors from "@fastify/cors";
import helmet from "@fastify/helmet";
import swagger from "@fastify/swagger";
import swaggerUI from "@fastify/swagger-ui";
import { prisma } from "./database/prisma";
import authContext from "./plugins/auth-context";
import { claimRoutes } from "./routes/claim.routes";
import { registerAllRoutes } from "./routes/all.routes";


export function buildApp() {
  const app = Fastify({
    logger: {
      level: env.LOG_LEVEL,
    },
  });

  // Security headers
  app.register(helmet);

  // CORS
  app.register(cors, {
    origin: true,
  });

  // Authentication request context
  app.register(authContext);

  // OpenAPI / Swagger
  app.register(swagger, {
    openapi: {
      info: {
        title: "TruthChain API",
        description: "Production API for the TruthChain platform",
        version: "1.0.0",
      },
      components: {
  securitySchemes: {
    bearerAuth: {
      type: "http",
      scheme: "bearer",
      bearerFormat: "JWT",
    },
  },
},
      tags: [
        {
          name: "system",
          description: "System and health endpoints",
        },
        {
          name: "claims",
          description: "Insurance claim management endpoints",
        },
      ],
    },
  });

  // Swagger UI
  app.register(swaggerUI, {
    routePrefix: "/docs",
  });

  // Health check
  app.get(
    "/health",
    {
      schema: {
        tags: ["system"],
        summary: "Health check",
        response: {
          200: {
            type: "object",
            properties: {
              status: { type: "string" },
              service: { type: "string" },
              timestamp: { type: "string" },
            },
          },
        },
      },
    },
    async () => {
      return {
        status: "ok",
        service: "truthchain-backend",
        timestamp: new Date().toISOString(),
      };
    },
  );

  // Readiness check
  app.get(
    "/ready",
    {
      schema: {
        tags: ["system"],
        summary: "Readiness check",
        response: {
          200: {
            type: "object",
            properties: {
              ready: { type: "boolean" },
              service: { type: "string" },
              database: { type: "string" },
            },
          },
          503: {
            type: "object",
            properties: {
              ready: { type: "boolean" },
              service: { type: "string" },
              database: { type: "string" },
            },
          },
        },
      },
    },
    async (_request, reply) => {
      try {
        await prisma.$queryRaw`SELECT 1`;

        return {
          ready: true,
          service: "truthchain-backend",
          database: "ok",
        };
      } catch (error) {
        app.log.error(
          error,
          "Database readiness check failed",
        );

        return reply.code(503).send({
          ready: false,
          service: "truthchain-backend",
          database: "unavailable",
        });
      }
    },
  );

  // API routes
  app.register(claimRoutes, {
    prefix: "/api/v1",
  });
  app.register(registerAllRoutes);

  return app;
}