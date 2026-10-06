import type { FastifyInstance } from "fastify";
import {
  createClaimController,
  getClaimController,
} from "../controllers/claim.controller";

export async function claimRoutes(
  app: FastifyInstance,
) {
  app.post(
    "/claims",
    {
      schema: {
        tags: ["claims"],
        summary: "Create a claim",
        description:
          "Create a new insurance claim within the authenticated organization.",
        security: [{ bearerAuth: [] }],
        body: {
          type: "object",
          required: ["claimNumber"],
          properties: {
            claimNumber: {
              type: "string",
              minLength: 1,
              maxLength: 100,
            },
            domain: {
              type: "string",
              enum: ["MOTOR"],
              default: "MOTOR",
            },
            description: {
              type: "string",
              maxLength: 5000,
            },
            submittedById: {
              type: "string",
              format: "uuid",
            },
          },
        },
      },
    },
    createClaimController,
  );

  app.get(
    "/claims/:id",
    {
      schema: {
        tags: ["claims"],
        summary: "Get a claim",
        description:
          "Retrieve a claim belonging to the authenticated organization.",
        security: [{ bearerAuth: [] }],
        params: {
          type: "object",
          required: ["id"],
          properties: {
            id: {
              type: "string",
              format: "uuid",
            },
          },
        },
      },
    },
    getClaimController,
  );
}