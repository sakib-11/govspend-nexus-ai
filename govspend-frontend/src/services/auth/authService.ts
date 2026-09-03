import { UserManager, WebStorageStateStore, User as OidcUser } from 'oidc-client-ts';
import { jwtDecode } from 'jwt-decode';
import { User, UserRole } from '../../types';

class AuthService {
  private userManager: UserManager | null = null;
  private static instance: AuthService;
  private isOidcConfigured: boolean = false;

  private constructor() {
    const authority = import.meta.env.VITE_OIDC_AUTHORITY;
    const clientId = import.meta.env.VITE_OIDC_CLIENT_ID;

    if (authority && clientId && typeof window !== 'undefined') {
      try {
        this.userManager = new UserManager({
          authority,
          client_id: clientId,
          redirect_uri: import.meta.env.VITE_OIDC_REDIRECT_URI || `${window.location.origin}/callback`,
          post_logout_redirect_uri:
            import.meta.env.VITE_OIDC_POST_LOGOUT_REDIRECT_URI || `${window.location.origin}/login`,
          response_type: 'code',
          scope: 'openid profile email roles jurisdictions',
          userStore: new WebStorageStateStore({ store: window.sessionStorage }),
          automaticSilentRenew: true,
          includeIdTokenInSilentRenew: true,
          loadUserInfo: true,
        });
        this.isOidcConfigured = true;
      } catch (err) {
        console.warn('OIDC initialization skipped or failed:', err);
      }
    }
  }

  static getInstance(): AuthService {
    if (!AuthService.instance) {
      AuthService.instance = new AuthService();
    }
    return AuthService.instance;
  }

  async login(): Promise<void> {
    if (this.userManager && this.isOidcConfigured) {
      try {
        await this.userManager.signinRedirect();
        return;
      } catch (err) {
        console.warn('OIDC redirect failed, falling back to demo login:', err);
      }
    }
    window.location.href = '/auditor/cases';
  }

  async logout(): Promise<void> {
    if (this.userManager && this.isOidcConfigured) {
      try {
        await this.userManager.signoutRedirect();
        return;
      } catch (err) {
        console.warn('OIDC signout failed:', err);
      }
    }
    window.location.href = '/login';
  }

  async handleCallback(): Promise<OidcUser | null> {
    if (this.userManager) {
      return await this.userManager.signinRedirectCallback();
    }
    return null;
  }

  async getUser(): Promise<OidcUser | null> {
    if (this.userManager) {
      return await this.userManager.getUser();
    }
    return null;
  }

  async getAccessToken(): Promise<string | null> {
    const oidcUser = await this.getUser();
    if (oidcUser?.access_token) {
      return oidcUser.access_token;
    }
    // Check local storage for demo token
    try {
      const stored = localStorage.getItem('govspend-auth-storage');
      if (stored) {
        const parsed = JSON.parse(stored);
        if (parsed.state?.token) {
          return parsed.state.token;
        }
      }
    } catch {
      // ignore
    }
    return null;
  }

  async isAuthenticated(): Promise<boolean> {
    const user = await this.getUser();
    if (user && !user.expired) return true;

    // Check store authentication state
    try {
      const stored = localStorage.getItem('govspend-auth-storage');
      if (stored) {
        const parsed = JSON.parse(stored);
        return !!parsed.state?.isAuthenticated;
      }
    } catch {
      // ignore
    }
    return false;
  }

  async renewToken(): Promise<OidcUser | null> {
    if (this.userManager) {
      return await this.userManager.signinSilent();
    }
    return null;
  }

  getDecodedToken(): any {
    try {
      const token = localStorage.getItem('govspend-token');
      if (token) {
        return jwtDecode(token);
      }
    } catch {
      return null;
    }
    return null;
  }
}

export default AuthService.getInstance();
