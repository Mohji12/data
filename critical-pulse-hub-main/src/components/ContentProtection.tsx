import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { isAdminRoute, isEditableElement } from '@/lib/contentProtection';

/**
 * Disables copy, cut, text selection, and common keyboard shortcuts on public and student pages.
 * Admin routes are excluded so staff can work normally.
 */
export default function ContentProtection() {
  const { pathname } = useLocation();
  const enabled = !isAdminRoute(pathname);

  useEffect(() => {
    document.body.classList.toggle('no-user-copy', enabled);
    return () => document.body.classList.remove('no-user-copy');
  }, [enabled]);

  useEffect(() => {
    if (!enabled) return;

    const allow = (target: EventTarget | null) => !isEditableElement(target);

    const blockMenu = (e: MouseEvent) => {
      if (allow(e.target)) e.preventDefault();
    };

    const blockClipboard = (e: ClipboardEvent) => {
      if (allow(e.target)) e.preventDefault();
    };

    const blockSelect = (e: Event) => {
      if (allow(e.target)) e.preventDefault();
    };

    const blockDrag = (e: DragEvent) => {
      if (allow(e.target)) e.preventDefault();
    };

    const blockKeys = (e: KeyboardEvent) => {
      if (!allow(e.target)) return;
      const mod = e.ctrlKey || e.metaKey;
      if (!mod) return;
      const key = e.key.toLowerCase();
      if (['c', 'x', 'a', 's', 'p', 'u'].includes(key)) {
        e.preventDefault();
      }
    };

    document.addEventListener('contextmenu', blockMenu);
    document.addEventListener('copy', blockClipboard);
    document.addEventListener('cut', blockClipboard);
    document.addEventListener('selectstart', blockSelect);
    document.addEventListener('dragstart', blockDrag);
    document.addEventListener('keydown', blockKeys);

    return () => {
      document.removeEventListener('contextmenu', blockMenu);
      document.removeEventListener('copy', blockClipboard);
      document.removeEventListener('cut', blockClipboard);
      document.removeEventListener('selectstart', blockSelect);
      document.removeEventListener('dragstart', blockDrag);
      document.removeEventListener('keydown', blockKeys);
    };
  }, [enabled]);

  return null;
}
