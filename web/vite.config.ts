import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 后端默认监听 127.0.0.1:8000（server/.env.example）
const BACKEND = process.env.VITE_BACKEND_ORIGIN ?? 'http://127.0.0.1:8000'

// 走 dev proxy 而不是浏览器直连后端：
// 请求变成同源，彻底绕开 CORS 与 Access-Control-Expose-Headers
// （D5 需要读 X-Request-Id / X-Upstream 响应头）。
const proxy = Object.fromEntries(
  ['/api', '/v1', '/health'].map((p) => [p, { target: BACKEND, changeOrigin: true }]),
)

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5173,
    proxy,
  },
})
