import { create } from 'zustand';
import { PolicyWeight, AuditLogEntry, User } from '../../types';

interface AdminState {
  policies: PolicyWeight[];
  activePolicy: PolicyWeight | null;
  users: User[];
  auditLogs: AuditLogEntry[];
  selectedAuditLog: AuditLogEntry | null;
  auditFilter: {
    userId: string;
    action: string;
    resourceType: string;
  };
  isLoading: boolean;
  error: string | null;

  // Actions
  setPolicies: (policies: PolicyWeight[]) => void;
  setActivePolicy: (policy: PolicyWeight | null) => void;
  setUsers: (users: User[]) => void;
  setAuditLogs: (logs: AuditLogEntry[]) => void;
  setSelectedAuditLog: (log: AuditLogEntry | null) => void;
  setAuditFilter: (filter: Partial<AdminState['auditFilter']>) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useAdminStore = create<AdminState>((set) => ({
  policies: [],
  activePolicy: null,
  users: [],
  auditLogs: [],
  selectedAuditLog: null,
  auditFilter: {
    userId: '',
    action: '',
    resourceType: '',
  },
  isLoading: false,
  error: null,

  setPolicies: (policies) => {
    const active = policies.find((p) => p.is_active) || null;
    set({ policies, activePolicy: active });
  },
  setActivePolicy: (activePolicy) => set({ activePolicy }),
  setUsers: (users) => set({ users }),
  setAuditLogs: (auditLogs) => set({ auditLogs }),
  setSelectedAuditLog: (selectedAuditLog) => set({ selectedAuditLog }),
  setAuditFilter: (filter) =>
    set((state) => ({ auditFilter: { ...state.auditFilter, ...filter } })),
  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
}));
