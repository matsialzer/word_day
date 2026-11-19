import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// В разработке запросы /api уходят на FastAPI (python -m worddays.web)
export default defineConfig({
  plugins: [vue()],
  server: { port: 5173, proxy: { '/api': 'http://127.0.0.1:8000' } },
  build: { outDir: 'dist', sourcemap: false },
})
