export const STUDENT_TOKEN_KEY = 'access_token';
export const ADMIN_TOKEN_KEY = 'admin_access_token';

/** Bearer token for API calls — admin sessionStorage first, then student localStorage. */
export function getAuthBearerToken(): string | null {
  return sessionStorage.getItem(ADMIN_TOKEN_KEY) || localStorage.getItem(STUDENT_TOKEN_KEY);
}

export function getStudentToken(): string | null {
  return localStorage.getItem(STUDENT_TOKEN_KEY);
}

export function setStudentToken(token: string): void {
  localStorage.setItem(STUDENT_TOKEN_KEY, token);
}

export function clearAdminToken(): void {
  sessionStorage.removeItem(ADMIN_TOKEN_KEY);
}

export function clearStudentToken(): void {
  localStorage.removeItem(STUDENT_TOKEN_KEY);
}

export function isExpiredTokenError(error: unknown): boolean {
  const message =
    error instanceof Error ? error.message : typeof error === 'string' ? error : '';
  const lower = message.toLowerCase();
  return lower.includes('invalid or expired token');
}

/** True when a student JWT is present and not past `exp` (small clock skew allowed). */
export function studentTokenLooksValid(token: string | null): boolean {
  if (!token || token.split('.').length < 2) return false;
  try {
    const payloadPart = token.split('.')[0];
    const padded = payloadPart.replace(/-/g, '+').replace(/_/g, '/') + '==';
    const json = atob(padded);
    const payload = JSON.parse(json) as { exp?: number };
    const exp = Number(payload?.exp || 0);
    if (!exp) return true;
    return exp * 1000 > Date.now() - 60_000;
  } catch {
    return Boolean(token);
  }
}
