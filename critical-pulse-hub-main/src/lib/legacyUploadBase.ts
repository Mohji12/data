import { getApiBaseUrl } from '@/lib/apiBase';

/** Hosts that must not be used for FastAPI registration uploads (files live on the API server). */
const MARKETING_DOC_HOSTS = new Set(['harishcriticalcareclasses.com', 'www.harishcriticalcareclasses.com']);

const DOC_PATH = '/upload/user/document_file/';

/**
 * Public base URL for registration documents (must be the FastAPI host, e.g. https://krintixsample.site).
 * Set VITE_DOCUMENT_PUBLIC_BASE_URL in production if it differs from VITE_API_URL.
 */
export function documentPublicBaseUrl(): string {
  const explicit = (import.meta.env.VITE_DOCUMENT_PUBLIC_BASE_URL as string | undefined)?.trim().replace(/\/$/, '');
  if (explicit) return explicit;
  return getApiBaseUrl().replace(/\/$/, '');
}

/**
 * @deprecated Use documentPublicBaseUrl(). Kept for old PHP-only files on the marketing site.
 */
export function legacyUploadBaseUrl(): string {
  const fromEnv = (import.meta.env.VITE_LEGACY_UPLOAD_BASE_URL as string | undefined)?.replace(/\/$/, '');
  if (fromEnv) return fromEnv;
  return documentPublicBaseUrl();
}

/** Extract plain filename from DB value or a full document URL (any host). */
export function registrationDocumentFilename(stored: string | null | undefined): string | null {
  const v = (stored || '').trim();
  if (!v) return null;
  if (!v.startsWith('http://') && !v.startsWith('https://')) {
    return v.includes('/') ? null : v;
  }
  try {
    const u = new URL(v);
    const path = u.pathname;
    const lower = path.toLowerCase();
    const marker = DOC_PATH.toLowerCase();
    const idx = lower.indexOf(marker);
    if (idx === -1) return null;
    const name = path.slice(idx + DOC_PATH.length);
    return name ? decodeURIComponent(name) : null;
  } catch {
    return null;
  }
}

export function resolveAdminDocumentHref(
  apiUrl: string | null | undefined,
  filename: string | null | undefined,
): string | null {
  const fn =
    registrationDocumentFilename(filename) ||
    registrationDocumentFilename(apiUrl) ||
    null;

  if (fn) {
    const base = documentPublicBaseUrl();
    if (base) {
      return `${base}${DOC_PATH}${encodeURIComponent(fn)}`;
    }
  }

  const u = (apiUrl || '').trim();
  if (!u) return null;

  try {
    const parsed = new URL(u);
    if (MARKETING_DOC_HOSTS.has(parsed.hostname.toLowerCase())) {
      const name = registrationDocumentFilename(u);
      const base = documentPublicBaseUrl();
      if (name && base) {
        return `${base}${DOC_PATH}${encodeURIComponent(name)}`;
      }
    }
  } catch {
    /* not a URL */
  }

  return u;
}
