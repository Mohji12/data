import { getApiBaseUrl } from '@/lib/apiBase';
import { isSessionInvalidError, notifySessionInvalidated } from '@/lib/sessionEvents';
const STUDENT_TOKEN_KEY = 'access_token';
const ADMIN_TOKEN_KEY = 'admin_access_token';

export async function apiClient(endpoint: string, options: RequestInit = {}) {
  const token = sessionStorage.getItem(ADMIN_TOKEN_KEY) || localStorage.getItem(STUDENT_TOKEN_KEY);
  
  const headers = new Headers(options.headers || {});
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(`${getApiBaseUrl()}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorMessage = 'An error occurred';
    try {
      const errorData = await response.json();
      // FastAPI usually returns errors under "detail"
      errorMessage = errorData.detail || errorData.message || errorMessage;
    } catch (e) {
      errorMessage = `HTTP error ${response.status}`;
    }
    if (response.status === 401 && isSessionInvalidError(errorMessage)) {
      notifySessionInvalidated();
    }
    throw new Error(typeof errorMessage === 'string' ? errorMessage : JSON.stringify(errorMessage));
  }

  if (response.status === 204) {
    return null;
  }
  
  return response.json();
}

/** Download a binary file (e.g. PDF) with auth headers. */
export async function apiDownload(
  endpoint: string,
  filename: string,
): Promise<void> {
  const token = sessionStorage.getItem(ADMIN_TOKEN_KEY) || localStorage.getItem(STUDENT_TOKEN_KEY);
  const headers = new Headers();
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(`${getApiBaseUrl()}${endpoint}`, { headers });
  if (!response.ok) {
    let errorMessage = 'Download failed';
    try {
      const errorData = await response.json();
      errorMessage = errorData.detail || errorData.message || errorMessage;
    } catch {
      errorMessage = `HTTP error ${response.status}`;
    }
    throw new Error(typeof errorMessage === 'string' ? errorMessage : JSON.stringify(errorMessage));
  }

  const buffer = await response.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  const isPdf =
    bytes.length >= 4 &&
    bytes[0] === 0x25 &&
    bytes[1] === 0x50 &&
    bytes[2] === 0x44 &&
    bytes[3] === 0x46;
  if (!isPdf) {
    let detail = 'Server did not return a valid PDF file.';
    try {
      const text = new TextDecoder().decode(bytes.slice(0, 500));
      const parsed = JSON.parse(text) as { detail?: string; message?: string };
      detail = parsed.detail || parsed.message || detail;
    } catch {
      // keep generic message
    }
    throw new Error(detail);
  }

  const blob = new Blob([buffer], { type: 'application/pdf' });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}
