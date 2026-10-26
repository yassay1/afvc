import { loadEnv } from 'vite'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'AFVC_')
  const target = env.AFVC_API_PROXY_TARGET || 'http://127.0.0.1:8000'

  return {
    plugins: [react()],
    server: {
      proxy: Object.fromEntries(
        ['/usecases', '/interaction', '/upload', '/health', '/auth'].map((path) => [path, { target, changeOrigin: true }]),
      ),
    },
    test: {
      include: ['src/**/*.test.{ts,tsx}'],
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
    },
  }
})
