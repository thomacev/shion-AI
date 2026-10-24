import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.DEV_API_TARGET || 'http://127.0.0.1:8000'
  return {
    plugins: [react(), tailwindcss()],
    server: {
      proxy: {
        // Preserve /auth/refresh so the backend's scoped refresh cookie works.
        '/auth': { target, changeOrigin: true },
        '/assistants': { target, changeOrigin: true },
      },
    },
  }
})
