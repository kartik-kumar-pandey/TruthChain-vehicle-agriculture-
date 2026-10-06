import type { FastifyReply, FastifyRequest } from "fastify";
import { Prisma } from "../generated/prisma/client";
import { createClaimSchema } from "../schemas/claim.schema";
import {
  createClaim,
  getClaimById,
} from "../services/claim.service";
import { requireAuth } from "../middleware/require-auth";

type CreateClaimRequest = FastifyRequest<{
  Body: unknown;
}>;

type GetClaimRequest = FastifyRequest<{
  Params: {
    id: string;
  };
}>;

export async function createClaimController(
  request: CreateClaimRequest,
  reply: FastifyReply,
) {
  await requireAuth(request, reply);

  if (!request.user) {
    return;
  }

  const parsed = createClaimSchema.safeParse(request.body);

  if (!parsed.success) {
    return reply.code(400).send({
      error: "VALIDATION_ERROR",
      message: "Invalid claim payload",
      details: parsed.error.flatten(),
    });
  }

  try {
    const claim = await createClaim(
      request.user.organizationId,
      parsed.data,
    );

    return reply.code(201).send({
      claim,
    });
  } catch (error) {
    if (
      error instanceof Prisma.PrismaClientKnownRequestError &&
      error.code === "P2002"
    ) {
      return reply.code(409).send({
        error: "CLAIM_ALREADY_EXISTS",
        message:
          "A claim with this claim number already exists for this organization",
      });
    }

    request.log.error(
      error,
      "Failed to create claim",
    );

    return reply.code(500).send({
      error: "CLAIM_CREATION_FAILED",
      message: "Unable to create claim",
    });
  }
}

export async function getClaimController(
  request: GetClaimRequest,
  reply: FastifyReply,
) {
  await requireAuth(request, reply);

  if (!request.user) {
    return;
  }

  const { id } = request.params;

  try {
    const claim = await getClaimById(
      request.user.organizationId,
      id,
    );

    if (!claim) {
      return reply.code(404).send({
        error: "CLAIM_NOT_FOUND",
        message: "Claim not found",
      });
    }

    return reply.send({
      claim,
    });
  } catch (error) {
    request.log.error(
      error,
      "Failed to retrieve claim",
    );

    return reply.code(500).send({
      error: "CLAIM_RETRIEVAL_FAILED",
      message: "Unable to retrieve claim",
    });
  }
}