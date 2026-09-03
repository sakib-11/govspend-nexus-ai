import apiClient from './apiClient';
import {
  Case,
  CaseDetail,
  CaseDetailResponse,
  CaseListResponse,
  CaseActionRequest,
} from '../../types';
import { MOCK_CASES, MOCK_CASE_DETAIL, MOCK_EVIDENCE_ITEMS } from './mockData';

export const caseService = {
  async getCases(params: {
    page?: number;
    limit?: number;
    tiers?: string[];
    statuses?: string[];
    department?: string;
    vendor_token?: string;
    minScore?: number;
    maxScore?: number;
    search?: string;
  }): Promise<CaseListResponse> {
    try {
      const page = params.page || 1;
      const limit = params.limit || 10;
      const offset = (page - 1) * limit;

      const queryParams: any = {
        limit,
        offset,
      };

      if (params.tiers && params.tiers.length > 0) {
        queryParams.tier = params.tiers;
      }
      if (params.statuses && params.statuses.length > 0) {
        queryParams.status = params.statuses;
      }
      if (params.department) {
        queryParams.department = params.department;
      }
      if (params.search) {
        queryParams.search = params.search;
      }
      if (params.minScore !== undefined) {
        queryParams.min_score = params.minScore;
      }
      if (params.maxScore !== undefined) {
        queryParams.max_score = params.maxScore;
      }

      const res = await apiClient.get<any>('/api/cases', { params: queryParams });
      if (res && Array.isArray(res.cases)) {
        return {
          cases: res.cases,
          total: res.total,
          limit: res.limit,
          offset: res.offset,
        };
      }
    } catch {
      // Fallback to local mock data with filtering
    }

    // Filter mock data locally
    let filtered = [...MOCK_CASES];

    if (params.tiers && params.tiers.length > 0) {
      filtered = filtered.filter((c) => params.tiers!.includes(c.tier));
    }
    if (params.statuses && params.statuses.length > 0) {
      filtered = filtered.filter((c) => params.statuses!.includes(c.status));
    }
    if (params.department) {
      const deptLower = params.department.toLowerCase();
      filtered = filtered.filter((c) => c.department.toLowerCase().includes(deptLower));
    }
    if (params.search) {
      const s = params.search.toLowerCase();
      filtered = filtered.filter(
        (c) =>
          c.case_id.toLowerCase().includes(s) ||
          c.transaction_id.toLowerCase().includes(s) ||
          c.vendor_token.toLowerCase().includes(s) ||
          c.department.toLowerCase().includes(s)
      );
    }
    if (params.minScore !== undefined) {
      filtered = filtered.filter((c) => c.risk_score >= params.minScore!);
    }
    if (params.maxScore !== undefined) {
      filtered = filtered.filter((c) => c.risk_score <= params.maxScore!);
    }

    const page = params.page || 1;
    const limit = params.limit || 10;
    const offset = (page - 1) * limit;
    const paged = filtered.slice(offset, offset + limit);

    return {
      cases: paged,
      total: filtered.length,
      limit,
      offset,
    };
  },

  async getCaseDetail(caseId: string): Promise<CaseDetailResponse> {
    try {
      const caseData = await apiClient.get<CaseDetail>(`/api/cases/${caseId}`);
      let evidence = MOCK_EVIDENCE_ITEMS;
      try {
        const evRes = await apiClient.get<any>(`/api/evidence/case/${caseId}`);
        if (evRes?.evidence) {
          evidence = evRes.evidence;
        }
      } catch {
        // use fallback evidence
      }
      return {
        case: caseData,
        evidence: evidence || [],
        actions: caseData.actions || [],
      };
    } catch {
      // Return enhanced mock detail
      const baseCase = MOCK_CASES.find((c) => c.case_id === caseId) || MOCK_CASES[0];
      const detail: CaseDetail = {
        ...MOCK_CASE_DETAIL,
        case_id: baseCase.case_id,
        transaction_id: baseCase.transaction_id,
        risk_score: baseCase.risk_score,
        tier: baseCase.tier,
        status: baseCase.status,
        department: {
          department_name: baseCase.department,
          jurisdiction: 'state-california',
        },
        vendor: {
          vendor_token: baseCase.vendor_token,
          masked_name: `Vendor Entity (${baseCase.vendor_token})`,
        },
        signals: baseCase.top_signals,
      };

      return {
        case: detail,
        evidence: MOCK_EVIDENCE_ITEMS,
        actions: detail.actions,
      };
    }
  },

  async approveCase(caseId: string, data: CaseActionRequest): Promise<any> {
    try {
      return await apiClient.post(`/api/cases/${caseId}/approve`, data);
    } catch {
      return {
        case_id: caseId,
        action: 'approve',
        status: 'APPROVED',
        timestamp: new Date().toISOString(),
        performed_by: 'auditor',
        message: 'Case approved successfully (Mock)',
      };
    }
  },

  async rejectCase(caseId: string, data: CaseActionRequest): Promise<any> {
    try {
      return await apiClient.post(`/api/cases/${caseId}/reject`, data);
    } catch {
      return {
        case_id: caseId,
        action: 'reject',
        status: 'REJECTED',
        timestamp: new Date().toISOString(),
        performed_by: 'auditor',
        message: 'Case rejected (Mock)',
      };
    }
  },

  async escalateCase(caseId: string, data: CaseActionRequest): Promise<any> {
    try {
      return await apiClient.post(`/api/cases/${caseId}/escalate`, data);
    } catch {
      return {
        case_id: caseId,
        action: 'escalate',
        status: 'ESCALATED',
        timestamp: new Date().toISOString(),
        performed_by: 'auditor',
        message: 'Case escalated to Senior Audit Board (Mock)',
      };
    }
  },

  async closeCase(caseId: string, data: CaseActionRequest): Promise<any> {
    try {
      return await apiClient.post(`/api/cases/${caseId}/close`, data);
    } catch {
      return {
        case_id: caseId,
        action: 'close',
        status: 'CLOSED',
        timestamp: new Date().toISOString(),
        performed_by: 'auditor',
        message: 'Case marked as resolved and closed (Mock)',
      };
    }
  },
};
