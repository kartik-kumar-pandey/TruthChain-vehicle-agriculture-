-- CreateEnum
CREATE TYPE "OrganizationStatus" AS ENUM ('ACTIVE', 'SUSPENDED', 'DELETED');

-- CreateEnum
CREATE TYPE "UserRole" AS ENUM ('ORGANIZATION_ADMIN', 'INVESTIGATOR', 'REVIEWER', 'AUDITOR');

-- CreateEnum
CREATE TYPE "UserStatus" AS ENUM ('ACTIVE', 'SUSPENDED', 'DELETED');

-- CreateEnum
CREATE TYPE "ClaimDomain" AS ENUM ('MOTOR');

-- CreateEnum
CREATE TYPE "ClaimStatus" AS ENUM ('SUBMITTED', 'QUEUED', 'PROCESSING', 'COMPLETED', 'REVIEW_REQUIRED', 'FAILED', 'CANCELLED');

-- CreateEnum
CREATE TYPE "AssessmentStatus" AS ENUM ('PROCESSING', 'COMPLETED', 'REVIEW_REQUIRED', 'FAILED');

-- CreateEnum
CREATE TYPE "AgentRunStatus" AS ENUM ('QUEUED', 'RUNNING', 'COMPLETED', 'FAILED', 'SKIPPED');

-- CreateEnum
CREATE TYPE "EvidenceType" AS ENUM ('EVIDENCE', 'CONTRADICTION', 'OBSERVATION', 'REASONING');

-- CreateEnum
CREATE TYPE "BlockchainStatus" AS ENUM ('PENDING', 'REGISTERED', 'ALREADY_REGISTERED', 'FAILED');

-- CreateTable
CREATE TABLE "organizations" (
    "id" UUID NOT NULL,
    "name" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "status" "OrganizationStatus" NOT NULL DEFAULT 'ACTIVE',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "organizations_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "users" (
    "id" UUID NOT NULL,
    "organizationId" UUID NOT NULL,
    "externalAuthId" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "firstName" TEXT,
    "lastName" TEXT,
    "role" "UserRole" NOT NULL DEFAULT 'INVESTIGATOR',
    "status" "UserStatus" NOT NULL DEFAULT 'ACTIVE',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "users_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "claims" (
    "id" UUID NOT NULL,
    "organizationId" UUID NOT NULL,
    "claimNumber" TEXT NOT NULL,
    "domain" "ClaimDomain" NOT NULL DEFAULT 'MOTOR',
    "status" "ClaimStatus" NOT NULL DEFAULT 'SUBMITTED',
    "description" TEXT,
    "submittedById" UUID,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "completedAt" TIMESTAMP(3),

    CONSTRAINT "claims_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "claim_images" (
    "id" UUID NOT NULL,
    "claimId" UUID NOT NULL,
    "storageProvider" TEXT NOT NULL,
    "storageKey" TEXT NOT NULL,
    "originalFilename" TEXT,
    "mimeType" TEXT NOT NULL,
    "fileSizeBytes" BIGINT NOT NULL,
    "sha256Hash" CHAR(64) NOT NULL,
    "width" INTEGER,
    "height" INTEGER,
    "imageType" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "claim_images_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "sensor_readings" (
    "id" UUID NOT NULL,
    "claimId" UUID NOT NULL,
    "source" TEXT,
    "payload" JSONB NOT NULL,
    "capturedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "sensor_readings_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "assessments" (
    "id" UUID NOT NULL,
    "claimId" UUID NOT NULL,
    "status" "AssessmentStatus" NOT NULL DEFAULT 'PROCESSING',
    "finalVerdict" TEXT,
    "fraudScore" DECIMAL(5,2),
    "modelVersion" TEXT,
    "startedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "completedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "assessments_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "agent_runs" (
    "id" UUID NOT NULL,
    "assessmentId" UUID NOT NULL,
    "agentName" TEXT NOT NULL,
    "status" "AgentRunStatus" NOT NULL,
    "decision" TEXT,
    "confidence" DECIMAL(6,5),
    "riskScore" DECIMAL(6,5),
    "modelVersion" TEXT,
    "processingTimeMs" INTEGER,
    "errorCode" TEXT,
    "errorMessage" TEXT,
    "startedAt" TIMESTAMP(3),
    "completedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "agent_runs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "agent_evidence" (
    "id" UUID NOT NULL,
    "agentRunId" UUID NOT NULL,
    "evidenceType" "EvidenceType" NOT NULL,
    "content" TEXT NOT NULL,
    "metadata" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "agent_evidence_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "risk_scores" (
    "id" UUID NOT NULL,
    "assessmentId" UUID NOT NULL,
    "imageRisk" DECIMAL(6,5),
    "sensorRisk" DECIMAL(6,5),
    "textRisk" DECIMAL(6,5),
    "crossModalRisk" DECIMAL(6,5),
    "investigationRisk" DECIMAL(6,5),
    "verifierRisk" DECIMAL(6,5),
    "finalScore" DECIMAL(5,2),
    "decision" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "risk_scores_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "blockchain_records" (
    "id" UUID NOT NULL,
    "assessmentId" UUID NOT NULL,
    "network" TEXT NOT NULL,
    "contractAddress" TEXT NOT NULL,
    "recordId" TEXT NOT NULL,
    "transactionHash" TEXT,
    "blockNumber" BIGINT,
    "imageHash" TEXT,
    "predictionHash" TEXT,
    "status" "BlockchainStatus" NOT NULL,
    "recorderAddress" TEXT,
    "registeredAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "blockchain_records_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "audit_events" (
    "id" UUID NOT NULL,
    "organizationId" UUID,
    "userId" UUID,
    "claimId" UUID,
    "eventType" TEXT NOT NULL,
    "entityType" TEXT,
    "entityId" UUID,
    "metadata" JSONB,
    "ipAddress" TEXT,
    "userAgent" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "audit_events_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "organizations_slug_key" ON "organizations"("slug");

-- CreateIndex
CREATE INDEX "users_organizationId_idx" ON "users"("organizationId");

-- CreateIndex
CREATE UNIQUE INDEX "users_organizationId_externalAuthId_key" ON "users"("organizationId", "externalAuthId");

-- CreateIndex
CREATE UNIQUE INDEX "users_organizationId_email_key" ON "users"("organizationId", "email");

-- CreateIndex
CREATE INDEX "claims_organizationId_idx" ON "claims"("organizationId");

-- CreateIndex
CREATE INDEX "claims_status_idx" ON "claims"("status");

-- CreateIndex
CREATE INDEX "claims_createdAt_idx" ON "claims"("createdAt");

-- CreateIndex
CREATE UNIQUE INDEX "claims_organizationId_claimNumber_key" ON "claims"("organizationId", "claimNumber");

-- CreateIndex
CREATE INDEX "claim_images_claimId_idx" ON "claim_images"("claimId");

-- CreateIndex
CREATE INDEX "claim_images_sha256Hash_idx" ON "claim_images"("sha256Hash");

-- CreateIndex
CREATE INDEX "sensor_readings_claimId_idx" ON "sensor_readings"("claimId");

-- CreateIndex
CREATE UNIQUE INDEX "assessments_claimId_key" ON "assessments"("claimId");

-- CreateIndex
CREATE INDEX "assessments_status_idx" ON "assessments"("status");

-- CreateIndex
CREATE INDEX "assessments_finalVerdict_idx" ON "assessments"("finalVerdict");

-- CreateIndex
CREATE INDEX "agent_runs_assessmentId_idx" ON "agent_runs"("assessmentId");

-- CreateIndex
CREATE INDEX "agent_runs_agentName_idx" ON "agent_runs"("agentName");

-- CreateIndex
CREATE INDEX "agent_runs_status_idx" ON "agent_runs"("status");

-- CreateIndex
CREATE INDEX "agent_evidence_agentRunId_idx" ON "agent_evidence"("agentRunId");

-- CreateIndex
CREATE INDEX "risk_scores_assessmentId_idx" ON "risk_scores"("assessmentId");

-- CreateIndex
CREATE UNIQUE INDEX "blockchain_records_assessmentId_key" ON "blockchain_records"("assessmentId");

-- CreateIndex
CREATE INDEX "blockchain_records_transactionHash_idx" ON "blockchain_records"("transactionHash");

-- CreateIndex
CREATE INDEX "blockchain_records_network_idx" ON "blockchain_records"("network");

-- CreateIndex
CREATE UNIQUE INDEX "blockchain_records_network_recordId_key" ON "blockchain_records"("network", "recordId");

-- CreateIndex
CREATE INDEX "audit_events_organizationId_idx" ON "audit_events"("organizationId");

-- CreateIndex
CREATE INDEX "audit_events_userId_idx" ON "audit_events"("userId");

-- CreateIndex
CREATE INDEX "audit_events_claimId_idx" ON "audit_events"("claimId");

-- CreateIndex
CREATE INDEX "audit_events_eventType_idx" ON "audit_events"("eventType");

-- CreateIndex
CREATE INDEX "audit_events_createdAt_idx" ON "audit_events"("createdAt");

-- AddForeignKey
ALTER TABLE "users" ADD CONSTRAINT "users_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "organizations"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "claims" ADD CONSTRAINT "claims_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "organizations"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "claims" ADD CONSTRAINT "claims_submittedById_fkey" FOREIGN KEY ("submittedById") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "claim_images" ADD CONSTRAINT "claim_images_claimId_fkey" FOREIGN KEY ("claimId") REFERENCES "claims"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "sensor_readings" ADD CONSTRAINT "sensor_readings_claimId_fkey" FOREIGN KEY ("claimId") REFERENCES "claims"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "assessments" ADD CONSTRAINT "assessments_claimId_fkey" FOREIGN KEY ("claimId") REFERENCES "claims"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "agent_runs" ADD CONSTRAINT "agent_runs_assessmentId_fkey" FOREIGN KEY ("assessmentId") REFERENCES "assessments"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "agent_evidence" ADD CONSTRAINT "agent_evidence_agentRunId_fkey" FOREIGN KEY ("agentRunId") REFERENCES "agent_runs"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "risk_scores" ADD CONSTRAINT "risk_scores_assessmentId_fkey" FOREIGN KEY ("assessmentId") REFERENCES "assessments"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "blockchain_records" ADD CONSTRAINT "blockchain_records_assessmentId_fkey" FOREIGN KEY ("assessmentId") REFERENCES "assessments"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "audit_events" ADD CONSTRAINT "audit_events_organizationId_fkey" FOREIGN KEY ("organizationId") REFERENCES "organizations"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "audit_events" ADD CONSTRAINT "audit_events_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "audit_events" ADD CONSTRAINT "audit_events_claimId_fkey" FOREIGN KEY ("claimId") REFERENCES "claims"("id") ON DELETE SET NULL ON UPDATE CASCADE;
