import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  server: {
    proxy: {
      // 브라우저는 /gms 로만 호출 -> Vite가 서버에서 gms.ssafy.io로 대신 호출 (CORS 회피)
      "/gms": {
        target: "https://gms.ssafy.io",
        changeOrigin: true,
        secure: true,
        rewrite: (path) => path.replace(/^\/gms/, ""),
      },
    },
  },
})
