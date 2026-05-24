export const SESSION_INVALIDATED_EVENT = 'session:invalidated';

export const SESSION_INVALID_MESSAGE = 'Logged in on another device';

export function isSessionInvalidError(error: unknown): boolean {
  const message =
    error instanceof Error ? error.message : typeof error === 'string' ? error : '';
  return message.toLowerCase().includes('another device');
}

export function notifySessionInvalidated(): void {
  window.dispatchEvent(new CustomEvent(SESSION_INVALIDATED_EVENT));
}
