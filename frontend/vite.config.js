import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: true,
    port: 5173,
    // 개발 중에는 /api 요청을 FastAPI로 넘긴다 (docker compose 에서는 BACKEND_URL=http://backend:8000)
    proxy: { '/api': process.env.BACKEND_URL || 'http://localhost:8000' },
  },
})
