import { OfficerMetrics, OfficerReport } from '../../types';
import { MOCK_OFFICER_METRICS, MOCK_OFFICER_REPORTS } from './mockData';

export const officerService = {
  async getMetrics(): Promise<OfficerMetrics> {
    return MOCK_OFFICER_METRICS;
  },

  async getReports(): Promise<OfficerReport[]> {
    return MOCK_OFFICER_REPORTS;
  },

  async generateReport(params: { period: string; title: string }): Promise<OfficerReport> {
    const newReport: OfficerReport = {
      id: `rep-${Date.now()}`,
      title: params.title,
      generated_at: new Date().toISOString(),
      period: params.period,
      summary: `Automated on-demand procurement risk synthesis for ${params.period}.`,
      total_spend: 18500000,
      flagged_spend: 1420000,
      compliance_score: 94.2,
      status: 'published',
    };
    MOCK_OFFICER_REPORTS.unshift(newReport);
    return newReport;
  },
};
