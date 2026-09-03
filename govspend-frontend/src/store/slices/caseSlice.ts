import { create } from 'zustand';
import { Case, CaseFilters, Pagination } from '../../types';

interface CaseState {
  cases: Case[];
  selectedCase: Case | null;
  filters: CaseFilters;
  pagination: Pagination;
  isLoading: boolean;
  error: string | null;

  // Actions
  setCases: (cases: Case[]) => void;
  setSelectedCase: (selectedCase: Case | null) => void;
  setFilters: (filters: CaseFilters) => void;
  resetFilters: () => void;
  setPagination: (pagination: Pagination) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  clearCases: () => void;
}

const initialFilters: CaseFilters = {
  tiers: [],
  statuses: [],
  department: '',
  vendor_token: '',
  minScore: 0,
  maxScore: 1,
  dateFrom: null,
  dateTo: null,
  search: '',
};

export const useCaseStore = create<CaseState>((set) => ({
  cases: [],
  selectedCase: null,
  filters: initialFilters,
  pagination: {
    page: 1,
    limit: 10,
    total: 0,
  },
  isLoading: false,
  error: null,

  setCases: (cases) => set({ cases }),
  setSelectedCase: (selectedCase) => set({ selectedCase }),
  setFilters: (filters) => set((state) => ({ filters: { ...state.filters, ...filters } })),
  resetFilters: () => set({ filters: initialFilters }),
  setPagination: (pagination) => set({ pagination }),
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
  clearCases: () => set({ cases: [], selectedCase: null }),
}));
