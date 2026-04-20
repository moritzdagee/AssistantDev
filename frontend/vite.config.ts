import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

// Build-Output: frontend/dist/
// web_server.py serviert von dort, sobald vorhanden.
// dev-Server: http://localhost:5173 mit Proxy auf das laufende Backend (:8080).
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      // Alle Nicht-HTML-Routen gehen an das laufende Python-Backend
      '/chat': 'http://localhost:8080',
      '/send': 'http://localhost:8080',
      '/messages': 'http://localhost:8080',
      '/conversations': 'http://localhost:8080',
      '/agents': 'http://localhost:8080',
      '/models': 'http://localhost:8080',
      '/search': 'http://localhost:8080',
      '/download_file': 'http://localhost:8080',
      '/upload_file': 'http://localhost:8080',
      '/memory': 'http://localhost:8080',
      '/working_memory': 'http://localhost:8080',
      '/capabilities': 'http://localhost:8080',
      '/permissions': 'http://localhost:8080',
      '/slack': 'http://localhost:8080',
      '/canva': 'http://localhost:8080',
      '/calendar': 'http://localhost:8080',
      '/changelog': 'http://localhost:8080',
      '/docs': 'http://localhost:8080',
      '/api': 'http://localhost:8080',
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: true,
    target: 'es2022',
  },
});
