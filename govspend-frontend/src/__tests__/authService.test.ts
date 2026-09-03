import { describe, it, expect, beforeEach } from 'vitest';
import authService from '../services/auth/authService';
import { useAuthStore, DEMO_USERS } from '../store';

describe('AuthService & AuthStore', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('should initialize with default demo user', () => {
    const user = useAuthStore.getState().user;
    expect(user).toBeDefined();
    expect(user?.user_id).toBe(DEMO_USERS.auditor_l3.user_id);
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
  });

  it('should switch user persona to Super Admin correctly', () => {
    useAuthStore.getState().loginAsDemoUser('super_admin');
    const user = useAuthStore.getState().user;
    expect(user?.user_id).toBe(DEMO_USERS.super_admin.user_id);
    expect(user?.roles).toContain('super_admin');
    expect(user?.roles).toContain('admin');
  });

  it('should switch user persona to Government Officer correctly', () => {
    useAuthStore.getState().loginAsDemoUser('officer');
    const user = useAuthStore.getState().user;
    expect(user?.user_id).toBe(DEMO_USERS.officer.user_id);
    expect(user?.roles).toContain('officer');
  });

  it('should handle logout correctly', () => {
    useAuthStore.getState().logout();
    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(useAuthStore.getState().token).toBeNull();
  });
});
