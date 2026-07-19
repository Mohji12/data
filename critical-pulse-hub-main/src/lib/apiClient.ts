import { getApiBaseUrl } from '@/lib/apiBase';
import {
  ADMIN_TOKEN_KEY,
  STUDENT_TOKEN_KEY,
  getAuthBearerToken,
  isExpiredTokenError,
  setStudentToken,
} from '@/lib/authToken';
import { isSessionInvalidError, notifySessionInvalidated } from '@/lib/sessionEvents';

type ApiClientOptions = RequestInit & { _retried?: boolean };

async function tryRefreshStudentToken(): Promise<boolean> {
  // Do not refresh while an admin session is active in this tab.
  if (sessionStorage.getItem(ADMIN_TOKEN_KEY)) return false;
  const current = localStorage.getItem(STUDENT_TOKEN_KEY);
  if (!current) return false;

  try {
    const response = await fetch(`${getApiBaseUrl()}/auth/session/refresh`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${current}`,
        'Content-Type': 'application/json',
      },
    });
    if (!response.ok) return false;
    const data = (await response.json()) as { access_token?: string };
    if (!data?.access_token) return false;
    setStudentToken(data.access_token);
    return true;
  } catch {
    return false;
  }
}

export async function refreshStudentSession(): Promise<boolean> {
  return tryRefreshStudentToken();
}

export async function apiClient(endpoint: string, options: ApiClientOptions = {}) {
  const token = getAuthBearerToken();

  const headers = new Headers(options.headers || {});
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const { _retried, ...fetchOptions } = options;
  const response = await fetch(`${getApiBaseUrl()}${endpoint}`, {
    ...fetchOptions,
    headers,
  });

  if (!response.ok) {
    let errorMessage = 'An error occurred';
    try {
      const errorData = await response.json();
      // FastAPI usually returns errors under "detail"
      errorMessage = errorData.detail || errorData.message || errorMessage;
    } catch {
      errorMessage = `HTTP error ${response.status}`;
    }
    if (response.status === 401 && isSessionInvalidError(errorMessage)) {
      notifySessionInvalidated();
    } else if (
      response.status === 401 &&
      !_retried &&
      isExpiredTokenError(errorMessage) &&
      !endpoint.includes('/auth/session/refresh') &&
      !endpoint.includes('/auth/login')
    ) {
      const refreshed = await tryRefreshStudentToken();
      if (refreshed) {
        return apiClient(endpoint, { ...options, _retried: true });
      }
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
  const token = getAuthBearerToken();
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
    if (response.status === 401 && isExpiredTokenError(errorMessage)) {
      const refreshed = await tryRefreshStudentToken();
      if (refreshed) {
        return apiDownload(endpoint, filename);
      }
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
