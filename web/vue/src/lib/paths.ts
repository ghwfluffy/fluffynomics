const normalizeBasePath = (value?: string) => {
  const raw = (value || '/').trim() || '/'
  const withLeadingSlash = `/${raw.replace(/^\/+/, '')}`
  return withLeadingSlash.endsWith('/') ? withLeadingSlash : `${withLeadingSlash}/`
}

export const appBasePath = normalizeBasePath(import.meta.env.VITE_APP_BASE_PATH || import.meta.env.BASE_URL)

const appBasePathWithoutTrailingSlash = appBasePath === '/' ? '' : appBasePath.replace(/\/$/, '')

const normalizeConfiguredApiBase = (value?: string) => {
  if (!value) {
    return ''
  }
  return value.replace(/\/$/, '')
}

export const apiBasePath =
  normalizeConfiguredApiBase(import.meta.env.VITE_API_BASE_URL) || `${appBasePathWithoutTrailingSlash}/api`

export const publicUrl = (import.meta.env.VITE_PUBLIC_URL || '').replace(/\/$/, '')

export const assetUrl = (path: string) => `${appBasePath}${path.replace(/^\/+/, '')}`

export const apiUrl = (path: string) => `${apiBasePath}/${path.replace(/^\/+/, '')}`

export const absolutePublicUrl = (path: string) => {
  if (/^https?:\/\//i.test(path)) {
    return path
  }
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  if (publicUrl) {
    return `${publicUrl}${normalizedPath}`
  }
  return new URL(normalizedPath, window.location.origin).toString()
}
