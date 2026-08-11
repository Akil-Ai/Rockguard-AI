import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Proxy keeps the browser on a single origin in development, so the demo
    // works even if CORS or the API base URL is misconfigured.
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        configure: (proxy) => {
          // Vite answers an unreachable upstream with 500, which the client
          // reads as "the backend replied and is broken". Emit 503 instead so a
          // backend that is simply not up yet looks the same in development as
          // a sleeping instance does in production.
          proxy.on('error', (_err, _req, res) => {
            if (res && !res.headersSent && typeof res.writeHead === 'function') {
              res.writeHead(503, { 'Content-Type': 'application/json' })
              res.end(JSON.stringify({ detail: 'Backend not reachable on port 8000.' }))
            }
          })
        },
      },
    },
  },
})
