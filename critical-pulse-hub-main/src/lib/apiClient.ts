import { getApiBaseUrl } from '@/lib/apiBase';
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

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}
