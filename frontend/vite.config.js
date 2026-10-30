import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// plotly.js/lib/* (used for the small custom bundle with radar charts) expects Node's `global`
export default defineConfig({
  plugins: [react()],
  define: { global: 'globalThis' },
})