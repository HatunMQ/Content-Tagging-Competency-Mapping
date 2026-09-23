import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  base: '/absproxy/5173/',
  plugins: [react()],
  server: {
    allowedHosts: ['t05-ide.aidc.nadir.sh'],
    proxy: {
      // Forwards translation requests to Model D's kubectl port-forward
      // tunnel (localhost:8001 -> the model-d-qwen35-svc Kubernetes
      // Service). This runs server-side inside the Vite dev process, so it
      // never has to go through the browser's absproxy tunnel for a new
      // port — see src/lib/translate.js for the full explanation.
      // code-server's /absproxy/ tunnel does NOT strip its own prefix
      // before forwarding to Vite, so the proxy key must include it too.
      '/absproxy/5173/model-api': {
        target: 'http://localhost:8002', // kept in sync with switch_model.sh's registry for model D
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/absproxy\/5173\/model-api/, ''),
      },
    },
  },
})
