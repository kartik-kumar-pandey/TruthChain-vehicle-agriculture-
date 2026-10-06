export type UserRole =
  | "ORGANIZATION_ADMIN"
  | "INVESTIGATOR"
  | "REVIEWER"
  | "AUDITOR";

export type AuthenticatedUser = {
  id: string;
  organizationId: string;
  role: UserRole;

  /**
   * Better Auth subject / user ID (externalAuthId in database).
   */
  authUserId: string;

  /**
   * Token permissions/scopes.
   */
  permissions: string[];
};