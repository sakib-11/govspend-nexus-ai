import apiClient from './apiClient';
import {
  AdminMetrics,
  AuditLogEntry,
  PolicyWeight,
  PolicyWeightCreate,
  User,
  UserRoleUpdate,
} from '../../types';
import { MOCK_POLICIES, MOCK_AUDIT_LOGS } from './mockData';
import { DEMO_USERS } from '../../store/slices/authSlice';

export const adminService = {
  async getMetrics(): Promise<AdminMetrics> {
    return {
      totalCases: 248,
      highRisk: 34,
      borderline: 65,
      lowRisk: 149,
      totalAuditedAmount: 48500000,
      potentialSavings: 4210000,
      avgInferenceLatencyMs: 142,
      tierDistribution: [
        { name: 'High Risk', value: 34, color: '#DC2626' },
        { name: 'Borderline', value: 65, color: '#D97706' },
        { name: 'Low Risk', value: 149, color: '#16A34A' },
      ],
      casesOverTime: [
        { date: '2024-03-09', high: 4, borderline: 8, low: 18 },
        { date: '2024-03-10', high: 6, borderline: 11, low: 22 },
        { date: '2024-03-11', high: 5, borderline: 9, low: 20 },
        { date: '2024-03-12', high: 8, borderline: 14, low: 26 },
        { date: '2024-03-13', high: 3, borderline: 7, low: 21 },
        { date: '2024-03-14', high: 5, borderline: 10, low: 24 },
        { date: '2024-03-15', high: 3, borderline: 6, low: 18 },
      ],
      detectorDistribution: [
        { detector: 'Price Deviation', count: 88, avgScore: 0.84 },
        { detector: 'Duplicate Fuzzy', count: 42, avgScore: 0.79 },
        { detector: 'Vendor Graph', count: 36, avgScore: 0.81 },
        { detector: 'Contract Splitting', count: 29, avgScore: 0.72 },
        { detector: 'Timing Anomaly', count: 24, avgScore: 0.65 },
        { detector: 'Approval Velocity', count: 18, avgScore: 0.58 },
      ],
    };
  },

  async getPolicyWeights(): Promise<PolicyWeight[]> {
    try {
      const res = await apiClient.get<PolicyWeight[]>('/api/admin/policy-weights');
      if (res && Array.isArray(res)) {
        return res;
      }
    } catch {
      // fallback
    }
    return MOCK_POLICIES;
  },

  async createPolicyWeight(data: PolicyWeightCreate): Promise<PolicyWeight> {
    try {
      return await apiClient.post<PolicyWeight>('/api/admin/policy-weights', data);
    } catch {
      const newPolicy: PolicyWeight = {
        version: `v${(MOCK_POLICIES.length + 1).toFixed(1)}`,
        weights: data.weights,
        is_active: !!data.activate,
        created_at: new Date().toISOString(),
        created_by: 'admin_user',
        description: data.description || 'Custom calibrated weights',
      };
      if (data.activate) {
        MOCK_POLICIES.forEach((p) => (p.is_active = false));
      }
      MOCK_POLICIES.unshift(newPolicy);
      return newPolicy;
    }
  },

  async activatePolicyWeight(version: string): Promise<PolicyWeight> {
    MOCK_POLICIES.forEach((p) => {
      p.is_active = p.version === version;
    });
    const activated = MOCK_POLICIES.find((p) => p.version === version) || MOCK_POLICIES[0];
    return activated;
  },

  async getAuditLogs(params?: {
    userId?: string;
    action?: string;
    resourceType?: string;
    limit?: number;
    offset?: number;
  }): Promise<{ entries: AuditLogEntry[]; total: number }> {
    try {
      const res = await apiClient.get<{ entries: AuditLogEntry[]; total: number }>(
        '/api/admin/audit-log',
        { params }
      );
      if (res && Array.isArray(res.entries)) {
        return res;
      }
    } catch {
      // fallback
    }
    let filtered = [...MOCK_AUDIT_LOGS];
    if (params?.userId) {
      filtered = filtered.filter((e) => e.user_id.includes(params.userId!));
    }
    if (params?.action) {
      filtered = filtered.filter((e) =>
        e.action.toLowerCase().includes(params.action!.toLowerCase())
      );
    }
    if (params?.resourceType) {
      filtered = filtered.filter((e) => e.resource_type === params.resourceType);
    }
    return {
      entries: filtered,
      total: filtered.length,
    };
  },

  async listUsers(): Promise<User[]> {
    try {
      const res = await apiClient.get<{ users: any[]; total: number }>('/api/admin/users');
      if (res && Array.isArray(res.users)) {
        return res.users;
      }
    } catch {
      // fallback
    }
    return Object.values(DEMO_USERS);
  },

  async updateUserRoles(userId: string, data: UserRoleUpdate): Promise<any> {
    try {
      return await apiClient.put(`/api/admin/users/${userId}/roles`, data);
    } catch {
      return {
        user_id: userId,
        roles: data.roles,
        jurisdictions: data.jurisdictions,
        updated_at: new Date().toISOString(),
      };
    }
  },
};
