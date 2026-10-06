import { z } from "zod";

export const createClaimSchema = z.object({
  claimNumber: z
    .string()
    .trim()
    .min(1, "claimNumber is required")
    .max(100),

  domain: z
    .literal("MOTOR")
    .default("MOTOR"),

  description: z
    .string()
    .trim()
    .max(5000)
    .optional(),

  submittedById: z
    .uuid()
    .optional(),
});

export type CreateClaimInput = z.infer<typeof createClaimSchema>;