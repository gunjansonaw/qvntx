import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In development the API runs separately (uvicorn on :8000); proxying /api keeps the
// frontend code identical across dev, docker-compose (nginx proxy) and single-origin
// production deployments (FastAPI static serving on Heroku, rewrites on Vercel).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_DEV_API_TARGET ?? 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 900,
  },
  test: {
    environment: 'node',
  },
})
