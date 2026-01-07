import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    // Proxy removed: Using VITE_API_BASE_URL for direct backend calls
    // This allows apiClient to make requests directly to http://127.0.0.1:8000/api
  }
})

