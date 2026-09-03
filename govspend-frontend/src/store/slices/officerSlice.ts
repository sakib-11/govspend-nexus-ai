import { create } from 'zustand';
import { OfficerMetrics, OfficerReport } from '../../types';

interface OfficerState {
  metrics: OfficerMetrics | null;
  reports: OfficerReport[];
  selectedReport: OfficerReport | null;
  selectedDepartment: string;
  isLoading: boolean;
  error: string | null;

  // Actions
  setMetrics: (metrics: OfficerMetrics | null) => void;
  setReports: (reports: OfficerReport[]) => void;
  setSelectedReport: (report: OfficerReport | null) => void;
  setSelectedDepartment: (dept: string) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useOfficerStore = create<OfficerState>((set) => ({
  metrics: null,
  reports: [],
  selectedReport: null,
  selectedDepartment: 'all',
  isLoading: false,
  error: null,

  setMetrics: (metrics) => set({ metrics }),
  setReports: (reports) => set({ reports }),
  setSelectedReport: (selectedReport) => set({ selectedReport }),
  setSelectedDepartment: (selectedDepartment) => set({ selectedDepartment }),
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
}));
