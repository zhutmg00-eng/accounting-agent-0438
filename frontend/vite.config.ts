import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Editors and agents write files by staging them in a sibling temp directory and
// renaming them into place. When that scratch directory lands inside `src/`, the
// Node file watcher tries to watch it and dies with
// `EBUSY: resource busy or locked, watch '.../*.tmpdir/*.tmp'`, taking the whole
// dev server down. Ignore the scratch paths explicitly.
const isScratch = (path: string): boolean =>
  /\.tmpdir([\\/]|$)/.test(path) || /\.tmp$/.test(path) || /[\\/]\.~/.test(path)

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    watch: {
      ignored: isScratch
    },
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8501',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 1500
  }
})
