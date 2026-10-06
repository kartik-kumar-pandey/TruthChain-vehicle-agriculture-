import { prisma } from "../database/prisma";
import type { CreateClaimInput } from "../schemas/claim.schema";

export async function createClaim(
  organizationId: string,
  input: CreateClaimInput,
) {
  return prisma.claim.create({
    data: {
      claimNumber: input.claimNumber,
      domain: input.domain,
      description: input.description,

      organization: {
        connect: {
          id: organizationId,
        },
      },

      ...(input.submittedById
        ? {
            submittedBy: {
              connect: {
                id: input.submittedById,
              },
            },
          }
        : {}),
    },
  });
}

export async function getClaimById(
  organizationId: string,
  id: string,
) {
  return prisma.claim.findFirst({
    where: {
      id,
      organizationId,
    },
    include: {
      policy: true,
      images: true,
      sensorReadings: true,
      assessment: {
        include: {
          agentRuns: {
            include: {
              evidence: true,
            },
          },
          riskScores: true,
          blockchainRecord: true,
        },
      },
      processingJobs: true,
    },
  });
}