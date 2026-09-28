import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  server: {
    port: 5173,
  },
  build: {
    rollupOptions: {
      output: {
        // Keep the heavy, rarely-changing libs in their own long-lived chunks.
        manualChunks(id) {
          if (id.includes('node_modules/highlight.js')) return 'highlight'
          if (id.includes('node_modules/react-markdown') || id.includes('node_modules/mdast') || id.includes('node_modules/micromark') || id.includes('node_modules/remark') || id.includes('node_modules/unified') || id.includes('node_modules/character-')) {
            return 'markdown'
          }
          if (id.includes('node_modules/react-dom') || id.includes('node_modules/scheduler')) {
            return 'react'
          }
          return undefined
        },
      },
    },
  },
})
