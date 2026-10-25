import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig(({ command }) => {
  if (command === 'build') {
    const raw = (process.env.VITE_ECS_API_ORIGIN || '').trim();
    let url: URL;
    try { url = new URL(raw); } catch { throw new Error('VITE_ECS_API_ORIGIN must be configured as a real HTTPS origin for production builds.'); }
    if (url.protocol !== 'https:' || !url.hostname || url.username || url.password || (url.pathname !== '/' && url.pathname !== '') || url.search || url.hash || /(^|\.)example(\.|$)|(^|\.)(test|invalid|localhost)$|your-api-host|your-domain/i.test(url.hostname)) {
      throw new Error('VITE_ECS_API_ORIGIN must be a real HTTPS origin without credentials, paths, queries, fragments, or placeholders.');
    }
  }
  return { plugins: [react()], build: { outDir: 'dist', emptyOutDir: true }, test: { environment: 'jsdom', setupFiles: './src/test-setup.ts', restoreMocks: true } };
});
