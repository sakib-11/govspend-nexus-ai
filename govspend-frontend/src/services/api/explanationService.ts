import apiClient from './apiClient';
import { CaseExplanation } from '../../types';
import { MOCK_EXPLANATION } from './mockData';

export const explanationService = {
  async getExplanation(caseId: string): Promise<CaseExplanation> {
    try {
      const res = await apiClient.get<CaseExplanation>(`/api/explanation/case/${caseId}`);
      if (res && res.explanations) {
        return res;
      }
    } catch {
      // Fallback
    }
    return {
      ...MOCK_EXPLANATION,
      case_id: caseId,
    };
  },
};
