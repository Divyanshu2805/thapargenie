import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

import { cspPlugin } from './csp.config.js'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  return {
    plugins: [react(), tailwindcss(), cspPlugin(env)],
    build: {
      // Budget is 250 KB gzipped for the initial JS; the raw-size warning is noise.
      chunkSizeWarningLimit: 800,
      // Small font subsets must stay files: inlined as data: URLs they are refused by
      // the Content-Security-Policy (font-src 'self') and log an error on every page.
      assetsInlineLimit: (filePath) => (/\.woff2?$/.test(filePath) ? false : undefined),
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
