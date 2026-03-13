import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3819,
    proxy: {
      '/api': 'http://127.0.0.1:3818',
      '/ws': {
        target: 'ws://127.0.0.1:3818',
        ws: true,
      },
      '/health': 'http://127.0.0.1:3818',
    },
  },
})
