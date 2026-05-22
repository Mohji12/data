/** Same origin as apiClient for CSV/PDF download links (include Bearer via cookie not possible — use fetch+blob or open with token; exports use cookie-less GET with admin token in query is NOT supported). */
export function getApiBaseUrl(): string {
  return import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
}

/** Public static files mounted on the API (e.g. `/upload/brochures/...`) — prefix API base when the URL is relative. */
export function resolvePublicUploadUrl(pathOrUrl: string | null | undefined): string | null {
  const s = (pathOrUrl || '').trim();
  if (!s) return null;
  if (/^https?:\/\//i.test(s)) return s;
  const base = getApiBaseUrl().replace(/\/$/, '');
  const path = s.startsWith('/') ? s : `/${s}`;
  return `${base}${path}`;
}

/** Opens an admin export URL in a new tab with Authorization header via temporary fetch+blob (fallback: raw URL for endpoints that don't need auth — not used). */
export async function openAuthenticatedExport(pathWithQuery: string): Promise<void> {
  const token = localStorage.getItem('access_token');
  const url = `${getApiBaseUrl()}${pathWithQuery.startsWith('/') ? '' : '/'}${pathWithQuery}`;
  const res = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    throw new Error(`Export failed: ${res.status}`);
  }
  const blob = await res.blob();
  const dl = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = dl;
  a.download = pathWithQuery.split('/').pop()?.split('?')[0] || 'export.csv';
  a.click();
  URL.revokeObjectURL(dl);
}

/** PDF (or any binary) download with Bearer; opens in a new tab via blob URL. */
export async function openAuthenticatedPdf(pathWithQuery: string): Promise<void> {
  const token = localStorage.getItem('access_token');
  const url = `${getApiBaseUrl()}${pathWithQuery.startsWith('/') ? '' : '/'}${pathWithQuery}`;
  const res = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    throw new Error(`Download failed: ${res.status}`);
  }
  const blob = await res.blob();
  const dl = URL.createObjectURL(blob);
  window.open(dl, '_blank', 'noopener,noreferrer');
  setTimeout(() => URL.revokeObjectURL(dl), 60_000);
}
