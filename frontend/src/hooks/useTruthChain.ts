"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ConsensusRequest, ConsensusResponse } from "@/types/claim";
import type { BlockchainVerifyRequest } from "@/types/blockchain";

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: () => api.health(),
    retry: false,
    refetchInterval: 15000,
  });
}

export function useReady() {
  return useQuery({
    queryKey: ["ready"],
    queryFn: () => api.ready(),
    retry: false,
  });
}

export function useSystemInfo() {
  return useQuery({
    queryKey: ["system-info"],
    queryFn: () => api.systemInfo(),
    retry: false,
  });
}

export function useClaims() {
  return useQuery({
    queryKey: ["claims"],
    queryFn: () => api.listClaims(),
    retry: 1,
  });
}

export function useClaim(claimId: string | null | undefined) {
  return useQuery({
    queryKey: ["claim", claimId],
    queryFn: () => api.getClaim(claimId as string),
    enabled: Boolean(claimId),
    retry: 1,
  });
}

export function useEvaluateClaim() {
  const queryClient = useQueryClient();
  return useMutation<ConsensusResponse, Error, ConsensusRequest>({
    mutationFn: (payload) => api.evaluateClaim(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["claims"] });
    },
  });
}

export function useEvaluateAgricultureClaim() {
  const queryClient = useQueryClient();
  return useMutation<ConsensusResponse, Error, Record<string, unknown>>({
    mutationFn: (payload) => api.evaluateAgricultureClaim(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["claims"] });
    },
  });
}

export function useBlockchainStatus() {
  return useQuery({
    queryKey: ["blockchain-status"],
    queryFn: () => api.getBlockchainStatus(),
    retry: 1,
  });
}

export function useBlockchainRecords(limit = 50) {
  return useQuery({
    queryKey: ["blockchain-records", limit],
    queryFn: () => api.listBlockchainRecords(limit),
    retry: 1,
  });
}

export function useBlockchainRecord(recordId: string | null | undefined) {
  return useQuery({
    queryKey: ["blockchain-record", recordId],
    queryFn: () => api.getBlockchainRecord(recordId as string),
    enabled: Boolean(recordId),
    retry: 1,
  });
}

export function useVerifyBlockchainRecord() {
  return useMutation({
    mutationFn: (payload: BlockchainVerifyRequest) =>
      api.verifyBlockchainRecord(payload),
  });
}
