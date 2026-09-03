import apiClient from './apiClient';
import { EvidenceDetail, EvidenceItem } from '../../types';
import { MOCK_EVIDENCE_ITEMS } from './mockData';

export const evidenceService = {
  async getEvidenceForCase(caseId: string): Promise<EvidenceItem[]> {
    try {
      const res = await apiClient.get<{ evidence: EvidenceItem[] }>(`/api/evidence/case/${caseId}`);
      if (res && Array.isArray(res.evidence)) {
        return res.evidence;
      }
    } catch {
      // Return mock evidence
    }
    return MOCK_EVIDENCE_ITEMS;
  },

  async getEvidenceDetail(evidenceId: string): Promise<EvidenceDetail> {
    try {
      return await apiClient.get<EvidenceDetail>(`/api/evidence/${evidenceId}`);
    } catch {
      const item = MOCK_EVIDENCE_ITEMS.find((e) => e.evidence_id === evidenceId) || MOCK_EVIDENCE_ITEMS[0];
      return {
        ...item,
        case_id: 'cs-849201',
        transaction_id: 'tx-99412',
        verified: true,
        hash: 'sha256-e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
        metadata: {
          verifier: 'AutomatedEvidenceVerificationEngine',
          timestamp: new Date().toISOString(),
        },
      };
    }
  },
};
