import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  // Prebundle worker-only imports before camera use so Vite does not reload
  // the page to optimize MediaPipe during the first capture.
  optimizeDeps: { include: ['@mediapipe/tasks-vision'] },
  // The worker is a plain file under /workers, which the CDN caches for hours; the page asks for it by build.
  define: { __BUILD_ID__: JSON.stringify(Date.now().toString(36)) },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
      '/ws': { target: 'ws://127.0.0.1:8000', ws: true },
    },
  },
});
