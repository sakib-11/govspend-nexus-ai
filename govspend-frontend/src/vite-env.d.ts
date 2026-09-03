/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  readonly VITE_OIDC_AUTHORITY: string;
  readonly VITE_OIDC_CLIENT_ID: string;
  readonly VITE_OIDC_REDIRECT_URI: string;
  readonly VITE_OIDC_POST_LOGOUT_REDIRECT_URI: string;
  readonly VITE_WEBSOCKET_URL: string;
  readonly VITE_ENABLE_MOCK_FALLBACK: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
