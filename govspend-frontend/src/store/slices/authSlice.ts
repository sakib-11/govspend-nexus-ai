import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { User, UserRole } from '../../types';

export const DEMO_USERS: Record<string, User> = {
  super_admin: {
    user_id: 'user-005',
    username: 'eve_superadmin',
    email: 'eve@govspend.gov',
    full_name: 'Eve Washington (Super Admin)',
    roles: [UserRole.SUPER_ADMIN, UserRole.ADMIN],
    jurisdictions: ['federal', 'state-california', 'state-new-york', 'local-nyc'],
    permissions: ['all'],
    mfa_enabled: true,
  },
  admin: {
    user_id: 'user-004',
    username: 'dave_admin',
    email: 'dave@govspend.gov',
    full_name: 'Dave Miller (System Admin)',
    roles: [UserRole.ADMIN],
    jurisdictions: ['federal', 'state-california', 'state-new-york'],
    permissions: ['policies:write', 'users:write', 'audit:read'],
    mfa_enabled: true,
  },
  auditor_l3: {
    user_id: 'user-003',
    username: 'carol_auditor3',
    email: 'carol@audit.gov',
    full_name: 'Carol Danvers (Senior Auditor L3 & Approver)',
    roles: [UserRole.AUDITOR_LEVEL_3, UserRole.APPROVER],
    jurisdictions: ['federal', 'state-california', 'state-new-york'],
    permissions: ['cases:approve', 'cases:reject', 'cases:escalate', 'unmask:request'],
    mfa_enabled: true,
  },
  auditor_l2: {
    user_id: 'user-002',
    username: 'bob_auditor2',
    email: 'bob@audit.gov',
    full_name: 'Bob Vance (Auditor Level 2)',
    roles: [UserRole.AUDITOR_LEVEL_2],
    jurisdictions: ['federal', 'state-california'],
    permissions: ['cases:escalate', 'cases:read', 'unmask:request'],
    mfa_enabled: false,
  },
  auditor_l1: {
    user_id: 'user-001',
    username: 'alice_auditor1',
    email: 'alice@audit.gov',
    full_name: 'Alice Smith (Auditor Level 1)',
    roles: [UserRole.AUDITOR_LEVEL_1],
    jurisdictions: ['federal'],
    permissions: ['cases:read'],
    mfa_enabled: false,
  },
  officer: {
    user_id: 'user-006',
    username: 'frank_officer',
    email: 'frank@transport.gov',
    full_name: 'Frank Castle (Procurement Officer)',
    roles: [UserRole.OFFICER],
    jurisdictions: ['federal', 'state-california'],
    permissions: ['reports:read', 'officer:dashboard'],
    mfa_enabled: true,
  },
};

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  token: string | null;

  // Actions
  setUser: (user: User | null) => void;
  setAuthenticated: (status: boolean) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setToken: (token: string | null) => void;
  loginAsDemoUser: (persona: keyof typeof DEMO_USERS) => void;
  logout: () => void;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: DEMO_USERS.auditor_l3, // Default to Auditor L3 for richest initial experience
      isAuthenticated: true,
      isLoading: false,
      error: null,
      token: 'demo-bearer-token-auditor-l3',

      setUser: (user) => set({ user, isAuthenticated: !!user }),
      setAuthenticated: (status) => set({ isAuthenticated: status }),
      setLoading: (loading) => set({ isLoading: loading }),
      setError: (error) => set({ error }),
      setToken: (token) => set({ token }),
      loginAsDemoUser: (persona) => {
        const demoUser = DEMO_USERS[persona] || DEMO_USERS.auditor_l3;
        set({
          user: demoUser,
          isAuthenticated: true,
          token: `demo-token-${persona}`,
          error: null,
        });
      },
      logout: () =>
        set({
          user: null,
          isAuthenticated: false,
          token: null,
          error: null,
        }),
      clearError: () => set({ error: null }),
    }),
    {
      name: 'govspend-auth-storage',
    }
  )
);
