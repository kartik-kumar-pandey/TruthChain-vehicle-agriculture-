import type {
  FastifyReply,
  FastifyRequest,
} from "fastify";

import { requireAuth } from "./require-auth";

export function requirePermission(permission: string) {
  return async (
    request: FastifyRequest,
    reply: FastifyReply,
  ): Promise<boolean> => {
    if (!(await requireAuth(request, reply))) {
      return false;
    }

    if (!request.user!.permissions.includes(permission)) {
      await reply.code(403).send({
        error: "FORBIDDEN",
        message: "You do not have permission to perform this action",
      });

      return false;
    }

    return true;
  };
}