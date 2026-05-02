const normalizeBasePath = (value?: string) => {
  const raw = (value || '/').trim() || '/'
  const withLeadingSlash = `/${raw.replace(/^\/+/, '')}`
  return withLeadingSlash.endsWith('/') ? withLeadingSlash : `${withLeadingSlash}/`
}

export const appBasePath = normalizeBasePath(import.meta.env.VITE_APP_BASE_PATH || import.meta.env.BASE_URL)

const appBasePathWithoutTrailingSlash = appBasePath === '/' ? '' : appBasePath.replace(/\/$/, '')

const browserOrigin = () => (typeof window === 'undefined' ? '' : window.location.origin)

const sameHostBrowserRelativeUrl = (value: string) => {
  if (!/^https?:\/\//i.test(value) || typeof window === 'undefined') {
    return value
  }
  try {
    const parsed = new URL(value)
    if (parsed.host === window.location.host) {
      return `${parsed.pathname.replace(/\/$/, '')}${parsed.search}${parsed.hash}`
    }
  } catch {
    return value
  }
  return value
}

const normalizeConfiguredApiBase = (value?: string) => {
  if (!value) {
    return ''
  }
  return sameHostBrowserRelativeUrl(value).replace(/\/$/, '')
}

export const apiBasePath =
  normalizeConfiguredApiBase(import.meta.env.VITE_API_BASE_URL) || `${appBasePathWithoutTrailingSlash}/api`

const normalizePublicUrl = (value?: string) => {
  const normalized = (value || '').replace(/\/$/, '')
  if (!normalized || typeof window === 'undefined' || !/^https?:\/\//i.test(normalized)) {
    return normalized
  }
  try {
    const parsed = new URL(normalized)
    if (parsed.host === window.location.host) {
      return browserOrigin()
    }
  } catch {
    return normalized
  }
  return normalized
}

export const publicUrl = normalizePublicUrl(import.meta.env.VITE_PUBLIC_URL)

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
