import type {
  FastifyReply,
  FastifyRequest,
} from "fastify";

export async function requireAuth(
  request: FastifyRequest,
  reply: FastifyReply,
): Promise<boolean> {
  if (!request.user) {
    await reply.code(401).send({
      error: "UNAUTHENTICATED",
      message: "Authentication is required",
    });

    return false;
  }

  return true;
}