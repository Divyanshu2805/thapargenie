import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig(() => {
  return {
    plugins: [react(), tailwindcss()],
    build: {
      // Budget is 250 KB gzipped for the initial JS; the raw-size warning is noise.
      chunkSizeWarningLimit: 800,
    },
    resolve: {
      alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
    },
    test: {
      environment: 'happy-dom',
      include: ['src/**/*.test.{js,jsx}', '*.test.js'],
      setupFiles: './src/test/setup.js',
    },
  }
})
