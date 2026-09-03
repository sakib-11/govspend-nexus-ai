import apiClient from './apiClient';
import { VendorAnalysis, VendorGraph } from '../../types';
import { MOCK_VENDOR_GRAPH } from './mockData';

export const graphService = {
  async getVendorGraph(vendorToken: string, depth: number = 2): Promise<VendorGraph> {
    try {
      const res = await apiClient.get<VendorGraph>(`/api/graph/vendor/${vendorToken}`, {
        params: { depth },
      });
      if (res && res.nodes && res.nodes.length > 0) {
        return res;
      }
    } catch {
      // Fallback to mock graph
    }
    return MOCK_VENDOR_GRAPH;
  },

  async analyseVendor(vendorToken: string): Promise<VendorAnalysis> {
    try {
      return await apiClient.get<VendorAnalysis>(`/api/graph/vendor/${vendorToken}/analyse`);
    } catch {
      return {
        vendor_token: vendorToken,
        degree_centrality: 0.78,
        clustering_coefficient: 0.65,
        shell_risk_index: 0.84,
        connected_officials_count: 1,
        historical_contracts_value: 4850000,
        flagged_anomalies: [
          'Shared registered office with Shell Entity #2',
          'Beneficial ownership link to internal approving official',
          'Multiple rapid high-value awards within 72 hours',
        ],
      };
    }
  },
};
