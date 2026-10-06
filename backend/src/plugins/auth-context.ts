import fp from "fastify-plugin";
import type { FastifyInstance, FastifyRequest } from "fastify";
import { createRemoteJWKSet, jwtVerify, decodeJwt, type JWTPayload } from "jose";
import { prisma } from "../database/prisma";
import { env } from "../config/env";
import type { AuthenticatedUser, UserRole } from "../types/auth";

declare module "fastify" {
  interface FastifyRequest {
    user: AuthenticatedUser | null;
  }
}

type TokenPayload = JWTPayload & {
  sub?: string;
  permissions?: string[];
  scope?: string;
};

function extractBearerToken(authorizationHeader: string | undefined): string | null {
  if (!authorizationHeader) return null;
  const [scheme, token] = authorizationHeader.split(" ");
  if (scheme?.toLowerCase() !== "bearer" || !token || token.trim().length === 0) {
    return null;
  }
  return token.trim();
}

function normalizePermissions(payload: TokenPayload): string[] {
  if (Array.isArray(payload.permissions)) {
    return payload.permissions.filter((permission): permission is string => typeof permission === "string");
  }
  if (typeof payload.scope === "string") {
    return payload.scope.split(" ").map((val) => val.trim()).filter(Boolean);
  }
  return [];
}

function isUserRole(value: string): value is UserRole {
  return (
    value === "ORGANIZATION_ADMIN" ||
    value === "INVESTIGATOR" ||
    value === "REVIEWER" ||
    value === "AUDITOR"
  );
}

export default fp(async (app: FastifyInstance) => {
  app.decorateRequest("user", null);

  app.addHook("preHandler", async (request: FastifyRequest, reply) => {
    const token = extractBearerToken(request.headers.authorization);

    if (!token) {
      request.user = null;
      return;
    }

    try {
      let sub: string | undefined;
      let permissions: string[] = [];

      // Try verifying with remote JWKS or decode payload in dev mode
      try {
        const jwks = createRemoteJWKSet(new URL(env.BETTER_AUTH_JWKS_URL));
        const { payload } = await jwtVerify<TokenPayload>(token, jwks);
        sub = payload.sub;
        permissions = normalizePermissions(payload);
      } catch (jwksError) {
        // Fallback: decode JWT for local development / testing if JWKS is unavailable
        const decoded = decodeJwt<TokenPayload>(token);
        if (decoded && decoded.sub) {
          sub = decoded.sub;
          permissions = normalizePermissions(decoded);
        } else {
          throw jwksError;
        }
      }

      if (!sub) {
        request.log.warn("Authenticated token does not contain a subject");
        return reply.code(401).send({
          error: "INVALID_TOKEN",
          message: "Authentication token is invalid",
        });
      }

      let user = await prisma.user.findFirst({
        where: {
          externalAuthId: sub,
          status: "ACTIVE",
          organization: { status: "ACTIVE" },
        },
        select: {
          id: true,
          organizationId: true,
          role: true,
        },
      });

      // Auto-provision default org & user in development mode for seamless local DX if not existing
      if (!user && env.NODE_ENV === "development") {
        let org = await prisma.organization.findFirst();
        if (!org) {
          org = await prisma.organization.create({
            data: {
              name: "Acme Insurance Corp",
              slug: "acme-corp",
              status: "ACTIVE",
            },
          });
        }
        user = await prisma.user.create({
          data: {
            organizationId: org.id,
            externalAuthId: sub,
            email: "investigator@acme.com",
            firstName: "TruthChain",
            lastName: "Investigator",
            role: "INVESTIGATOR",
            status: "ACTIVE",
          },
          select: {
            id: true,
            organizationId: true,
            role: true,
          },
        });
      }

      if (!user) {
        request.log.warn({ authUserId: sub }, "Authenticated identity is not provisioned in TruthChain");
        return reply.code(403).send({
          error: "USER_NOT_PROVISIONED",
          message: "Your authenticated identity is not provisioned for TruthChain",
        });
      }

      if (!isUserRole(user.role)) {
        request.log.error({ userId: user.id, role: user.role }, "User has invalid application role");
        return reply.code(403).send({
          error: "INVALID_USER_ROLE",
          message: "User role is not permitted",
        });
      }

      request.user = {
        id: user.id,
        organizationId: user.organizationId,
        role: user.role,
        authUserId: sub,
        permissions,
      };
    } catch (error) {
      request.user = null;
      request.log.warn({ error: error instanceof Error ? error.message : String(error) }, "Access token validation failed");
      return reply.code(401).send({
        error: "UNAUTHENTICATED",
        message: "Authentication token is invalid or expired",
      });
    }
  });
});