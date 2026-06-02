import { getAuthBearerToken } from '@/lib/authToken';

/** Local FastAPI when developing against uvicorn on port 8000. */
export const LOCAL_DEV_API = 'http://127.0.0.1:8000';

/**
 * API base for fetch(). In dev with VITE_API_USE_PROXY=true, returns '' so requests
 * go to the Vite server (localhost:8080) and are proxied to VITE_API_URL (or :8000).
 */
export function getApiBaseUrl(): string {
  const useProxy = import.meta.env.VITE_API_USE_PROXY === 'true';
  if (import.meta.env.DEV && useProxy) {
    return '';
  }

  const raw = String(import.meta.env.VITE_API_URL ?? '').trim();
  const url = raw || LOCAL_DEV_API;
  return url.replace(/\/$/, '');
}

function getProxyTargetForDisplay(): string {
  const raw = String(import.meta.env.VITE_API_URL ?? '').trim();
  return raw.replace(/\/$/, '') || LOCAL_DEV_API;
}

/** For debugging in the browser console. */
export function getResolvedApiBaseForDisplay(): string {
  const base = getApiBaseUrl();
  if (base) return base;
  if (typeof window !== 'undefined') {
    return `${window.location.origin} → proxy → ${getProxyTargetForDisplay()}`;
  }
  return `(proxy) → ${getProxyTargetForDisplay()}`;
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

function resolveApiUrl(pathWithQuery: string): string {
  const path = pathWithQuery.startsWith('/') ? pathWithQuery : `/${pathWithQuery}`;
  return `${getApiBaseUrl()}${path}`;
}

function filenameFromContentDisposition(header: string | null, fallback: string): string {
  if (!header) return fallback;
  const star = /filename\*=UTF-8''([^;]+)/i.exec(header);
  if (star?.[1]) {
    try {
      return decodeURIComponent(star[1].trim());
    } catch {
      return star[1].trim();
    }
  }
  const plain = /filename="?([^";\n]+)"?/i.exec(header);
  return plain?.[1]?.trim() || fallback;
}

async function parseDownloadError(res: Response): Promise<string> {
  const text = await res.text();
  try {
    const parsed = JSON.parse(text) as { detail?: unknown; message?: string };
    if (typeof parsed.detail === 'string') return parsed.detail;
    if (parsed.message) return parsed.message;
  } catch {
    if (text.trim()) return text.slice(0, 200);
  }
  return `Download failed (${res.status})`;
}

/** Fetch CSV/XLSX/PDF with admin or student Bearer token and trigger a file save. */
export async function downloadAuthenticatedFile(
  pathWithQuery: string,
  defaultFilename?: string,
): Promise<void> {
  const token = getAuthBearerToken();
  if (!token) {
    throw new Error('Not signed in. Please log in again and retry the download.');
  }

  const fallback =
    defaultFilename || pathWithQuery.split('/').pop()?.split('?')[0] || 'download.bin';
  const res = await fetch(resolveApiUrl(pathWithQuery), {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!res.ok) {
    throw new Error(await parseDownloadError(res));
  }

  const blob = await res.blob();
  const filename = filenameFromContentDisposition(res.headers.get('Content-Disposition'), fallback);
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/** CSV/XLSX export with Authorization header (admin sessionStorage token supported). */
export async function openAuthenticatedExport(
  pathWithQuery: string,
  defaultFilename?: string,
): Promise<void> {
  await downloadAuthenticatedFile(pathWithQuery, defaultFilename);
}

/** PDF download with Bearer; opens in a new tab via blob URL. */
export async function openAuthenticatedPdf(pathWithQuery: string): Promise<void> {
  const token = getAuthBearerToken();
  if (!token) {
    throw new Error('Not signed in. Please log in again and retry the download.');
  }

  const res = await fetch(resolveApiUrl(pathWithQuery), {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new Error(await parseDownloadError(res));
  }

  const blob = await res.blob();
  const dl = URL.createObjectURL(blob);
  window.open(dl, '_blank', 'noopener,noreferrer');
  setTimeout(() => URL.revokeObjectURL(dl), 60_000);
}
