import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Uploaded listing photos are served by FastAPI on :8000. Proxying only
      // /uploads keeps image_url environment-independent — the database stores
      // "/uploads/x.jpg", and the browser resolves it against :5173 in dev.
      //
      // /api calls are NOT proxied. lib/api.ts still uses the absolute
      // http://localhost:8000 base URL, which already works.
      //
      // Production needs the equivalent /uploads rule in whatever server hosts
      // the frontend.
      '/uploads': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
