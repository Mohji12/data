/** True when the current path is the admin panel (copy/select allowed there). */
export function isAdminRoute(pathname: string): boolean {
  return pathname.startsWith('/admin');
}

/** Form fields where users may select or copy their own input. */
export function isEditableElement(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return !!target.closest('input, textarea, select, [contenteditable="true"]');
}
