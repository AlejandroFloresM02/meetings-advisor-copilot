import path from 'path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    // The UI dev server runs on 3000. Port 8000 is reserved for the FastAPI
    // backend (see the /api proxy below), so keep them separate.
    port: 3000,
    // Fail loudly instead of silently hopping to the next free port if 3000
    // is already taken.
    strictPort: true,
    // Forward API calls to the FastAPI backend so there are no CORS issues
    // in development. The browser talks only to the Vite dev server.
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
