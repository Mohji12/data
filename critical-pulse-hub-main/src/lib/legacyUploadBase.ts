/**
 * Fallback base for /upload/user/document_file/{filename} when the API omits presigned/full URLs.
 * Keep in sync with FastAPI: legacy_upload_base_url defaults to EMAIL_ASSET_BASE_URL / production site.
 */
export function legacyUploadBaseUrl(): string {
  const fromEnv = (import.meta.env.VITE_LEGACY_UPLOAD_BASE_URL as string | undefined)?.replace(/\/$/, '');
  if (fromEnv) return fromEnv;
  return 'https://harishcriticalcareclasses.com';
}

export function resolveAdminDocumentHref(
  apiUrl: string | null | undefined,
  filename: string | null | undefined,
): string | null {
  const u = (apiUrl || '').trim();
  if (u) return u;
  const fn = (filename || '').trim();
  if (!fn) return null;
  const api = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '');
  if (api && !fn.includes('/') && !fn.startsWith('http')) {
    return `${api}/upload/user/document_file/${encodeURIComponent(fn)}`;
  }
  const base = legacyUploadBaseUrl();
  return `${base}/upload/user/document_file/${encodeURIComponent(fn)}`;
}
