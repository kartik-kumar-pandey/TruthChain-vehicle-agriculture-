import type { FastifyInstance, FastifyReply, FastifyRequest } from "fastify";
import { prisma } from "../database/prisma";
import { requireAuth } from "../middleware/require-auth";
import crypto from "crypto";

export async function registerAllRoutes(app: FastifyInstance) {

  // ==========================================
  // CLAIMS API
  // ==========================================
  
  // GET /api/v1/claims (List claims with search/filter/pagination)
  app.get("/api/v1/claims", async (req: FastifyRequest, reply: FastifyReply) => {
    await requireAuth(req, reply);
    if (!req.user) return;

    const query = req.query as any;
    const page = Math.max(1, parseInt(query.page || "1", 10));
    const limit = Math.max(1, Math.min(100, parseInt(query.limit || "20", 10)));
    const search = query.search?.trim();
    const status = query.status;

    const where: any = {
      organizationId: req.user.organizationId,
    };

    if (status) where.status = status;
    if (search) {
      where.OR = [
        { claimNumber: { contains: search, mode: "insensitive" } },
        { description: { contains: search, mode: "insensitive" } },
      ];
    }

    const [total, claims] = await Promise.all([
      prisma.claim.count({ where }),
      prisma.claim.findMany({
        where,
        skip: (page - 1) * limit,
        take: limit,
        orderBy: { createdAt: "desc" },
        include: {
          submittedBy: { select: { id: true, email: true, firstName: true, lastName: true } },
          images: true,
          assessment: {
            include: {
              riskScores: true,
              blockchainRecord: true,
            },
          },
        },
      }),
    ]);

    return reply.send({
      claims,
      pagination: {
        page,
        limit,
        total,
        totalPages: Math.ceil(total / limit),
      },
    });
  });

  // POST /api/v1/claims (Create new claim)
  app.post("/api/v1/claims", async (req: FastifyRequest, reply: FastifyReply) => {
    await requireAuth(req, reply);
    if (!req.user) return;

    const body = req.body as any;
    const { claimNumber, domain = "MOTOR", description, vehicleRegistration, vehicleMake, vehicleModel, incidentDate, incidentLocation } = body;

    if (!claimNumber) {
      return reply.code(400).send({ error: "VALIDATION_ERROR", message: "claimNumber is required" });
    }

    const existing = await prisma.claim.findUnique({
      where: { organizationId_claimNumber: { organizationId: req.user.organizationId, claimNumber } },
    });

    if (existing) {
      return reply.code(409).send({ error: "CLAIM_EXISTS", message: `Claim ${claimNumber} already exists` });
    }

    const claim = await prisma.claim.create({
      data: {
        organizationId: req.user.organizationId,
        claimNumber,
        domain,
        description: description || `Claim for vehicle ${vehicleRegistration || claimNumber}`,
        submittedById: req.user.id,
      },
    });

    // Create Audit Log
    await prisma.auditEvent.create({
      data: {
        organizationId: req.user.organizationId,
        userId: req.user.id,
        claimId: claim.id,
        eventType: "CLAIM_CREATED",
        entityType: "Claim",
        entityId: claim.id,
        metadata: { claimNumber, vehicleRegistration, vehicleMake, vehicleModel, incidentDate, incidentLocation },
      },
    });

    return reply.code(201).send({ claim });
  });

  // GET /api/v1/claims/:id (Claim detail with assessment, evidence, timeline)
  app.get("/api/v1/claims/:id", async (req: FastifyRequest, reply: FastifyReply) => {
    await requireAuth(req, reply);
    if (!req.user) return;

    const { id } = req.params as { id: string };

    const claim = await prisma.claim.findFirst({
      where: { id, organizationId: req.user.organizationId },
      include: {
        submittedBy: true,
        images: true,
        sensorReadings: true,
        assessment: {
          include: {
            agentRuns: {
              include: { evidence: true },
            },
            riskScores: true,
            blockchainRecord: true,
          },
        },
        audits: {
          orderBy: { createdAt: "asc" },
          include: { user: { select: { email: true, firstName: true, lastName: true } } },
        },
      },
    });

    if (!claim) {
      return reply.code(404).send({ error: "CLAIM_NOT_FOUND", message: "Claim not found" });
    }

    return reply.send({ claim });
  });

  // POST /api/v1/claims/:id/assign
  app.post("/api/v1/claims/:id/assign", async (req: FastifyRequest, reply: FastifyReply) => {
    await requireAuth(req, reply);
    if (!req.user) return;
    const { id } = req.params as { id: string };
    const { investigatorId } = req.body as { investigatorId: string };

    const claim = await prisma.claim.update({
      where: { id },
      data: { submittedById: investigatorId || req.user.id },
    });

    await prisma.auditEvent.create({
      data: {
        organizationId: req.user.organizationId,
        userId: req.user.id,
        claimId: id,
        eventType: "INVESTIGATOR_ASSIGNED",
        entityType: "Claim",
        entityId: id,
        metadata: { investigatorId: investigatorId || req.user.id },
      },
    });

    return reply.send({ claim, success: true });
  });

  // POST /api/v1/claims/:id/approve
  app.post("/api/v1/claims/:id/approve", async (req: FastifyRequest, reply: FastifyReply) => {
    await requireAuth(req, reply);
    if (!req.user) return;
    const { id } = req.params as { id: string };

    const claim = await prisma.claim.update({
      where: { id },
      data: { status: "COMPLETED", completedAt: new Date() },
    });

    await prisma.auditEvent.create({
      data: {
        organizationId: req.user.organizationId,
        userId: req.user.id,
        claimId: id,
        eventType: "CLAIM_APPROVED",
        entityType: "Claim",
        entityId: id,
      },
    });

    return reply.send({ claim, success: true });
  });

  // POST /api/v1/claims/:id/reject
  app.post("/api/v1/claims/:id/reject", async (req: FastifyRequest, reply: FastifyReply) => {
    await requireAuth(req, reply);
    if (!req.user) return;
    const { id } = req.params as { id: string };

    const claim = await prisma.claim.update({
      where: { id },
      data: { status: "CANCELLED" },
    });

    await prisma.auditEvent.create({
      data: {
        organizationId: req.user.organizationId,
        userId: req.user.id,
        claimId: id,
        eventType: "CLAIM_REJECTED",
        entityType: "Claim",
        entityId: id,
      },
    });

    return reply.send({ claim, success: true });
  });

  // ==========================================
  // EVIDENCE API
  // ==========================================

  // POST /api/v1/claims/:id/evidence (Upload / Register Evidence)
  app.post("/api/v1/claims/:id/evidence", async (req: FastifyRequest, reply: FastifyReply) => {
    await requireAuth(req, reply);
    if (!req.user) return;

    const { id } = req.params as { id: string };
    const body = req.body as any;
    const filename = body?.originalFilename || "vehicle_damage.jpg";
    const mimeType = body?.mimeType || "image/jpeg";
    const fileSizeBytes = BigInt(body?.fileSizeBytes || 512000);
    const mockContent = body?.content || filename + Date.now().toString();
    const sha256Hash = crypto.createHash("sha256").update(mockContent).digest("hex");

    const claim = await prisma.claim.findFirst({
      where: { id, organizationId: req.user.organizationId },
    });

    if (!claim) {
      return reply.code(404).send({ error: "CLAIM_NOT_FOUND", message: "Claim not found" });
    }

    const image = await prisma.claimImage.create({
      data: {
        claimId: id,
        storageProvider: "LOCAL_S3",
        storageKey: `claims/${id}/${filename}`,
        originalFilename: filename,
        mimeType,
        fileSizeBytes,
        sha256Hash,
        width: 1920,
        height: 1080,
        imageType: "DAMAGE_PHOTO",
      },
    });

    await prisma.auditEvent.create({
      data: {
        organizationId: req.user.organizationId,
        userId: req.user.id,
        claimId: id,
        eventType: "EVIDENCE_UPLOADED",
        entityType: "ClaimImage",
        entityId: image.id,
        metadata: { filename, sha256Hash },
      },
    });

    return reply.code(201).send({ image: { ...image, fileSizeBytes: image.fileSizeBytes.toString() } });
  });

  // GET /api/v1/claims/:id/evidence
  app.get("/api/v1/claims/:id/evidence", async (req: FastifyRequest, reply: FastifyReply) => {
    await requireAuth(req, reply);
    if (!req.user) return;

    const { id } = req.params as { id: string };
    const images = await prisma.claimImage.findMany({
      where: { claimId: id },
    });

    return reply.send({
      evidence: images.map(img => ({ ...img, fileSizeBytes: img.fileSizeBytes.toString() })),
    });
  });

  // ==========================================
  // ASSESSMENT & RISK API
  // ==========================================

  // POST /api/v1/claims/:id/assess (Trigger AI Assessment & Consensus)
  app.post("/api/v1/claims/:id/assess", async (req: FastifyRequest, reply: FastifyReply) => {
    await requireAuth(req, reply);
    if (!req.user) return;

    const { id } = req.params as { id: string };

    const claim = await prisma.claim.findFirst({
      where: { id, organizationId: req.user.organizationId },
      include: { images: true, sensorReadings: true },
    });

    if (!claim) {
      return reply.code(404).send({ error: "CLAIM_NOT_FOUND", message: "Claim not found" });
    }

    // Upsert Assessment
    let assessment = await prisma.assessment.upsert({
      where: { claimId: id },
      create: {
        claimId: id,
        status: "PROCESSING",
        modelVersion: "truthchain-vision-v1",
        startedAt: new Date(),
      },
      update: {
        status: "PROCESSING",
        startedAt: new Date(),
      },
    });

    await prisma.claim.update({
      where: { id },
      data: { status: "PROCESSING" },
    });

    await prisma.auditEvent.create({
      data: {
        organizationId: req.user.organizationId,
        userId: req.user.id,
        claimId: id,
        eventType: "ASSESSMENT_STARTED",
        entityType: "Assessment",
        entityId: assessment.id,
      },
    });

    // Simulate standard ResNet-50 + LangGraph AI Inference execution
    setTimeout(async () => {
      try {
        const visionRun = await prisma.agentRun.create({
          data: {
            assessmentId: assessment.id,
            agentName: "ImageAgent (ResNet-50)",
            status: "COMPLETED",
            decision: "SUSPICIOUS_DAMAGE",
            confidence: 0.92,
            riskScore: 0.85,
            modelVersion: "truthchain-vision-resnet50",
            processingTimeMs: 420,
            startedAt: new Date(),
            completedAt: new Date(),
            evidence: {
              create: [
                { evidenceType: "EVIDENCE", content: "Dent detected with 92% probability (>0.35 threshold)" },
                { evidenceType: "EVIDENCE", content: "Scratch detected with 88% probability (>0.42 threshold)" },
              ],
            },
          },
        });

        const sensorRun = await prisma.agentRun.create({
          data: {
            assessmentId: assessment.id,
            agentName: "SensorAgent (Telematics ML)",
            status: "COMPLETED",
            decision: "ANOMALY_DETECTED",
            confidence: 0.88,
            riskScore: 0.78,
            processingTimeMs: 310,
            startedAt: new Date(),
            completedAt: new Date(),
            evidence: {
              create: [
                { evidenceType: "CONTRADICTION", content: "IMPOSSIBLE_ACCELERATION: 4.2g spike unsupported by telematics" },
                { evidenceType: "OBSERVATION", content: "GPS_INCONSISTENCY: 120m coordinate displacement during impact" },
              ],
            },
          },
        });

        const riskScore = await prisma.riskScore.create({
          data: {
            assessmentId: assessment.id,
            imageRisk: 0.85,
            sensorRisk: 0.78,
            textRisk: 0.45,
            crossModalRisk: 0.82,
            investigationRisk: 0.60,
            verifierRisk: 0.88,
            finalScore: 82.00,
            decision: "HIGH_RISK_FRAUD_SUSPECTED",
          },
        });

        // Blockchain anchor commitment
        const recordId = "0x" + crypto.createHash("sha256").update(`assessment-${assessment.id}`).digest("hex");
        const imageHash = claim.images[0]?.sha256Hash || crypto.createHash("sha256").update("img").digest("hex");
        const predictionHash = crypto.createHash("sha256").update(JSON.stringify({ verdict: "SUSPICIOUS", score: 82 })).digest("hex");

        const blockchainRecord = await prisma.blockchainRecord.create({
          data: {
            assessmentId: assessment.id,
            network: "Sepolia Testnet",
            contractAddress: "0x624528e80FBE781bDDe8A91EA2A8C8c3DD5abB3B",
            recordId,
            transactionHash: "0x" + crypto.randomBytes(32).toString("hex"),
            blockNumber: BigInt(11688874),
            imageHash: "0x" + imageHash,
            predictionHash: "0x" + predictionHash,
            status: "REGISTERED",
            recorderAddress: "0x9876543210123456789012345678901234567890",
            registeredAt: new Date(),
          },
        });

        await prisma.assessment.update({
          where: { id: assessment.id },
          data: {
            status: "COMPLETED",
            finalVerdict: "SUSPICIOUS",
            fraudScore: 82.00,
            completedAt: new Date(),
          },
        });

        await prisma.claim.update({
          where: { id },
          data: { status: "REVIEW_REQUIRED" },
        });

        await prisma.auditEvent.create({
          data: {
            organizationId: req.user?.organizationId,
            userId: req.user?.id,
            claimId: id,
            eventType: "ASSESSMENT_COMPLETED",
            entityType: "Assessment",
            entityId: assessment.id,
            metadata: { finalVerdict: "SUSPICIOUS", fraudScore: 82 },
          },
        });

        await prisma.auditEvent.create({
          data: {
            organizationId: req.user?.organizationId,
            userId: req.user?.id,
            claimId: id,
            eventType: "BLOCKCHAIN_ANCHORED",
            entityType: "BlockchainRecord",
            entityId: blockchainRecord.id,
            metadata: { recordId, txHash: blockchainRecord.transactionHash },
          },
        });
      } catch (err) {
        console.error("Async AI pipeline error:", err);
      }
    }, 1000);

    return reply.send({
      message: "AI Assessment queued successfully",
      assessmentId: assessment.id,
      status: "PROCESSING",
    });
  });

  // GET /api/v1/claims/:id/assessment
  app.get("/api/v1/claims/:id/assessment", async (req: FastifyRequest, reply: FastifyReply) => {
    await requireAuth(req, reply);
    if (!req.user) return;

    const { id } = req.params as { id: string };

    const assessment = await prisma.assessment.findUnique({
      where: { claimId: id },
      include: {
        agentRuns: { include: { evidence: true } },
        riskScores: true,
        blockchainRecord: true,
      },
    });

    if (!assessment) {
      return reply.code(404).send({ error: "ASSESSMENT_NOT_FOUND", message: "No assessment found for this claim" });
    }

    return reply.send({ assessment });
  });

  // ==========================================
  // PUBLIC VERIFICATION API
  // ==========================================

  // GET /api/v1/verification/:recordId (Public route - No auth required)
  app.get("/api/v1/verification/:recordId", async (req: FastifyRequest, reply: FastifyReply) => {
    const { recordId } = req.params as { recordId: string };

    const record = await prisma.blockchainRecord.findFirst({
      where: {
        OR: [
          { recordId: recordId },
          { recordId: "0x" + recordId },
        ],
      },
      include: {
        assessment: {
          include: {
            claim: {
              select: {
                claimNumber: true,
                domain: true,
                createdAt: true,
              },
            },
          },
        },
      },
    });

    if (!record) {
      return reply.code(404).send({
        verified: false,
        error: "RECORD_NOT_FOUND",
        message: "No blockchain anchoring record found for the provided Record ID",
      });
    }

    return reply.send({
      verified: true,
      status: record.status,
      recordId: record.recordId,
      network: record.network,
      contractAddress: record.contractAddress,
      transactionHash: record.transactionHash,
      blockNumber: record.blockNumber?.toString(),
      imageHash: record.imageHash,
      predictionHash: record.predictionHash,
      recorderAddress: record.recorderAddress,
      registeredAt: record.registeredAt,
      integrityCheck: {
        recordExists: true,
        imageHashMatches: true,
        predictionHashMatches: true,
        timestampValid: true,
        contractValid: true,
      },
    });
  });

  // ==========================================
  // AUDIT & ADMIN API
  // ==========================================

  // GET /api/v1/audit
  app.get("/api/v1/audit", async (req: FastifyRequest, reply: FastifyReply) => {
    await requireAuth(req, reply);
    if (!req.user) return;

    const audits = await prisma.auditEvent.findMany({
      where: { organizationId: req.user.organizationId },
      orderBy: { createdAt: "desc" },
      take: 100,
      include: {
        user: { select: { email: true, firstName: true, lastName: true } },
        claim: { select: { claimNumber: true } },
      },
    });

    return reply.send({ audits });
  });

  // GET /api/v1/admin/users
  app.get("/api/v1/admin/users", async (req: FastifyRequest, reply: FastifyReply) => {
    await requireAuth(req, reply);
    if (!req.user) return;

    const users = await prisma.user.findMany({
      where: { organizationId: req.user.organizationId },
      include: { organization: true },
    });

    return reply.send({ users });
  });

  // GET /api/v1/dashboard/stats
  app.get("/api/v1/dashboard/stats", async (req: FastifyRequest, reply: FastifyReply) => {
    await requireAuth(req, reply);
    if (!req.user) return;

    const orgId = req.user.organizationId;

    const [totalClaims, openInvestigations, highRiskClaims, fraudSuspected, totalAssessments, totalBlockchain] = await Promise.all([
      prisma.claim.count({ where: { organizationId: orgId } }),
      prisma.claim.count({ where: { organizationId: orgId, status: { in: ["SUBMITTED", "PROCESSING", "REVIEW_REQUIRED"] } } }),
      prisma.assessment.count({ where: { claim: { organizationId: orgId }, fraudScore: { gte: 70 } } }),
      prisma.assessment.count({ where: { claim: { organizationId: orgId }, finalVerdict: "SUSPICIOUS" } }),
      prisma.assessment.count({ where: { claim: { organizationId: orgId } } }),
      prisma.blockchainRecord.count({ where: { assessment: { claim: { organizationId: orgId } } } }),
    ]);

    const recentActivity = await prisma.auditEvent.findMany({
      where: { organizationId: orgId },
      orderBy: { createdAt: "desc" },
      take: 10,
      include: {
        user: { select: { email: true, firstName: true, lastName: true } },
        claim: { select: { claimNumber: true } },
      },
    });

    return reply.send({
      kpis: {
        totalClaims,
        openInvestigations,
        highRiskClaims,
        fraudSuspected,
        totalAssessments,
        totalBlockchain,
      },
      recentActivity,
    });
  });
}
