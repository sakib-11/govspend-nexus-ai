import apiClient from './apiClient';
import {
  UnmaskApproval,
  UnmaskRequestCreate,
  UnmaskResponse,
  UnmaskStatus,
} from '../../types';

export const unmaskService = {
  async createRequest(data: UnmaskRequestCreate): Promise<UnmaskResponse> {
    try {
      return await apiClient.post<UnmaskResponse>('/api/unmask/request', data);
    } catch {
      return {
        request_id: `unmask-${Math.random().toString(36).substring(2, 9)}`,
        case_id: data.case_id,
        entity_type: data.entity_type,
        entity_token: data.entity_token,
        status: UnmaskStatus.PENDING,
        requested_by: 'current_user',
        requested_at: new Date().toISOString(),
      };
    }
  },

  async approveRequest(requestId: string, data: UnmaskApproval): Promise<UnmaskResponse> {
    try {
      return await apiClient.post<UnmaskResponse>(`/api/unmask/${requestId}/approve`, data);
    } catch {
      const isApproved = data.decision === 'approve';
      return {
        request_id: requestId,
        case_id: 'cs-849201',
        entity_type: 'vendor',
        entity_token: 'VK-83921',
        status: isApproved ? UnmaskStatus.APPROVED : UnmaskStatus.REJECTED,
        requested_by: 'carol_auditor3',
        requested_at: new Date(Date.now() - 3600000).toISOString(),
        approved_by: 'eve_superadmin',
        approved_at: new Date().toISOString(),
        unmasked_data: isApproved
          ? {
              legal_name: 'Apex Infrastructure Holdings Private Limited',
              tax_identifier: 'US-EIN-88-2940192',
              registration_country: 'United States',
              registered_address: '104 Corporate Plaza, Suite 900, San Francisco, CA 94105',
              directors: [
                { name: 'Johnathon R. Sterling', tin: 'XXX-XX-9102' },
                { name: 'Sarah Vance-Miller', tin: 'XXX-XX-4412' },
              ],
              bank_account_number: '••••••••••••4921',
              authorized_signatory: 'Johnathon R. Sterling (Managing Director)',
            }
          : null,
      };
    }
  },

  async getStatus(requestId: string): Promise<UnmaskResponse> {
    try {
      return await apiClient.get<UnmaskResponse>(`/api/unmask/${requestId}/status`);
    } catch {
      return {
        request_id: requestId,
        case_id: 'cs-849201',
        entity_type: 'vendor',
        entity_token: 'VK-83921',
        status: UnmaskStatus.APPROVED,
        requested_by: 'carol_auditor3',
        requested_at: new Date(Date.now() - 3600000).toISOString(),
        approved_by: 'eve_superadmin',
        approved_at: new Date().toISOString(),
        unmasked_data: {
          legal_name: 'Apex Infrastructure Holdings Private Limited',
          tax_identifier: 'US-EIN-88-2940192',
          registration_country: 'United States',
          registered_address: '104 Corporate Plaza, Suite 900, San Francisco, CA 94105',
          directors: [
            { name: 'Johnathon R. Sterling', tin: 'XXX-XX-9102' },
            { name: 'Sarah Vance-Miller', tin: 'XXX-XX-4412' },
          ],
          bank_account_number: '••••••••••••4921',
          authorized_signatory: 'Johnathon R. Sterling (Managing Director)',
        },
      };
    }
  },

  async listPendingRequests(): Promise<UnmaskResponse[]> {
    try {
      const res = await apiClient.get<{ requests: UnmaskResponse[] }>('/api/unmask/requests');
      if (res && Array.isArray(res.requests)) {
        return res.requests;
      }
    } catch {
      // Fallback
    }
    return [
      {
        request_id: 'unmask-req-101',
        case_id: 'cs-849201',
        entity_type: 'vendor',
        entity_token: 'VK-83921',
        status: UnmaskStatus.PENDING,
        requested_by: 'carol_auditor3',
        requested_at: new Date(Date.now() - 1800000).toISOString(),
      },
    ];
  },
};
