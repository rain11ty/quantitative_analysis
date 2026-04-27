/// <reference types="vite/client" />

interface QuantAppAuthContext {
  isAuthenticated: boolean;
  isAdmin: boolean;
  displayName: string | null;
}

interface QuantAppBootstrapContext {
  auth: QuantAppAuthContext;
  initialPath: string;
}

interface Window {
  __QUANT_APP_CONTEXT__?: QuantAppBootstrapContext;
}
