import { defineStore } from 'pinia';
import { ref, computed } from 'vue';

export interface AuthState {
  isAuthenticated: boolean;
  isAdmin: boolean;
  displayName: string | null;
}

export const useAuthStore = defineStore('auth', () => {
  const ctx = window.__QUANT_APP_CONTEXT__?.auth;

  const isAuthenticated = ref(ctx?.isAuthenticated ?? false);
  const isAdmin = ref(ctx?.isAdmin ?? false);
  const displayName = ref(ctx?.displayName ?? null);

  const isGuest = computed(() => !isAuthenticated.value);

  function bootstrapFromContext() {
    const c = window.__QUANT_APP_CONTEXT__?.auth;
    if (c) {
      isAuthenticated.value = c.isAuthenticated;
      isAdmin.value = c.isAdmin;
      displayName.value = c.displayName;
    }
  }

  function setAuth(auth: Partial<AuthState>) {
    if (auth.isAuthenticated !== undefined) isAuthenticated.value = auth.isAuthenticated;
    if (auth.isAdmin !== undefined) isAdmin.value = auth.isAdmin;
    if (auth.displayName !== undefined) displayName.value = auth.displayName;
  }

  return { isAuthenticated, isAdmin, displayName, isGuest, bootstrapFromContext, setAuth };
});
