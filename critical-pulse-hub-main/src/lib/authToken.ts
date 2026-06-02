export const STUDENT_TOKEN_KEY = 'access_token';
export const ADMIN_TOKEN_KEY = 'admin_access_token';

/** Bearer token for API calls — admin sessionStorage first, then student localStorage. */
export function getAuthBearerToken(): string | null {
  return sessionStorage.getItem(ADMIN_TOKEN_KEY) || localStorage.getItem(STUDENT_TOKEN_KEY);
}
