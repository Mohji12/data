import { getApiBaseUrl } from '@/lib/apiBase';
const ADMIN_TOKEN_KEY = 'admin_access_token';

export async function fetchAdminDocumentBlob(userId: number, file: 1 | 2 = 1): Promise<Blob> {
  const token = sessionStorage.getItem(ADMIN_TOKEN_KEY);
  const headers = new Headers();
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(`${getApiBaseUrl()}/admin/users/${userId}/document?file=${file}`, { headers });
  if (!response.ok) {
    let detail = 'Could not load document';
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      detail = `HTTP ${response.status}`;
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return response.blob();
}

export function isPdfFilename(name?: string | null): boolean {
  return (name || '').toLowerCase().endsWith('.pdf');
}

export function isImageFilename(name?: string | null): boolean {
  return /\.(jpe?g|png|webp)$/i.test(name || '');
}
