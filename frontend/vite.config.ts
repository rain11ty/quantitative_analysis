import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

const backendTarget = 'http://127.0.0.1:5001';

export default defineConfig(({ command }) => ({
  base: command === 'serve' ? '/' : '/static/vue/',
  plugins: [vue()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': backendTarget,
      '/auth': backendTarget,
      '/admin': backendTarget,
      '/static': backendTarget,
    },
  },
  build: {
    outDir: '../app/static/vue',
    emptyOutDir: true,
    manifest: true,
  },
}));
