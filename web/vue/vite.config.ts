import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

const normalizeBasePath = (value?: string) => {
  const raw = (value || '/').trim() || '/'
  const withLeadingSlash = `/${raw.replace(/^\/+/, '')}`
  return withLeadingSlash.endsWith('/') ? withLeadingSlash : `${withLeadingSlash}/`
}

const appBasePath = normalizeBasePath(process.env.VITE_APP_BASE_PATH || process.env.APP_BASE_PATH)
const appBasePathWithoutTrailingSlash = appBasePath === '/' ? '' : appBasePath.replace(/\/$/, '')
const apiProxyPath = `${appBasePathWithoutTrailingSlash}/api`
const apiProxyPathPattern = apiProxyPath.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

// https://vitejs.dev/config/
export default defineConfig({
  base: appBasePath,
  plugins: [vue()],
  server: {
    proxy: {
      [apiProxyPath]: {
        target: process.env.VITE_DEV_API_TARGET || 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(new RegExp(`^${apiProxyPathPattern}`), ''),
      },
      ...(apiProxyPath === '/api'
        ? {}
        : {
            '/api': {
              target: process.env.VITE_DEV_API_TARGET || 'http://localhost:8000',
              changeOrigin: true,
              rewrite: (path) => path.replace(/^\/api/, ''),
            },
          }),
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  }
})
