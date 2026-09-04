import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const apiProxyTarget = process.env.VITE_DEV_API_PROXY || 'http://web:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    watch: {
      usePolling: true,
    },
    proxy: {
      // changeOrigin: false — Django строит абсолютные ссылки (аватары)
      // из заголовка Host. С подменой хоста он отдавал внутренний адрес
      // контейнера http://web:8000/media/..., который браузер не открывает.
      '/api': { target: apiProxyTarget, changeOrigin: false },
      // Медиа и статика: без проксирования загруженный аватар не открывался.
      '/media': { target: apiProxyTarget, changeOrigin: false },
      '/static': { target: apiProxyTarget, changeOrigin: false },
    },
  },
})
