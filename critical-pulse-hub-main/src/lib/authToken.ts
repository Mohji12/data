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
  return lower.includes('invalid or expired token') || lower.includes('missing authorization token');
}
