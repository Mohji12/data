import { useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { toast } from 'sonner';
import { isAdminRoute, isEditableElement } from '@/lib/contentProtection';
import { useAuthStore } from '@/store/authStore';

const SCREENSHOT_MSG = 'Screenshots are disabled on this website';

/**
 * Disables copy, cut, text selection, screenshot capture vectors, and common
 * keyboard shortcuts on public and student pages.
 * Admin routes are excluded so staff can work normally.
 */
export default function ContentProtection() {
  const { pathname } = useLocation();
  const enabled = !isAdminRoute(pathname);
  const [hidden, setHidden] = useState(false);
  const lastScreenshotToastAt = useRef(0);
  const flashTimerRef = useRef<number>(0);
  const viewer = useAuthStore((s) => s.user);

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

    const wipeClipboard = () => {
      // Replace the captured frame with empty content.
      try {
        void navigator.clipboard?.writeText(' ').catch(() => {});
      } catch {
        /* clipboard API unavailable */
      }
    };

    // Cover the page with the brand screen for a few seconds — any capture
    // taken right after PrintScreen grabs the logo, not the content.
    const flashCover = () => {
      setHidden(true);
      if (flashTimerRef.current) window.clearTimeout(flashTimerRef.current);
      flashTimerRef.current = window.setTimeout(() => setHidden(false), 4000);
    };

    const warnScreenshot = () => {
      flashCover();
      // keydown and keyup can both fire for PrintScreen — show one toast.
      const now = Date.now();
      if (now - lastScreenshotToastAt.current > 1500) {
        lastScreenshotToastAt.current = now;
        toast.warning(SCREENSHOT_MSG);
      }
    };

    const blockKeys = (e: KeyboardEvent) => {
      if (!allow(e.target)) return;
      if (e.key === 'PrintScreen') {
        e.preventDefault();
        wipeClipboard();
        warnScreenshot();
        return;
      }
      const mod = e.ctrlKey || e.metaKey;
      if (!mod) return;
      const key = e.key.toLowerCase();
      if (['c', 'x', 'a', 's', 'p', 'u'].includes(key)) {
        e.preventDefault();
      }
    };

    const onKeyUp = (e: KeyboardEvent) => {
      // Some browsers only emit keyup for PrintScreen.
      if (e.key === 'PrintScreen') {
        wipeClipboard();
        warnScreenshot();
      }
    };

    // Hide page content while the window is unfocused — snipping tools
    // (Win+Shift+S, Snipping Tool, third-party capturers) steal focus, so
    // the capture grabs this overlay instead of the page.
    const hide = () => setHidden(true);
    const show = () => setHidden(false);
    const onVisibility = () => setHidden(document.hidden);

    document.addEventListener('contextmenu', blockMenu);
    document.addEventListener('copy', blockClipboard);
    document.addEventListener('cut', blockClipboard);
    document.addEventListener('selectstart', blockSelect);
    document.addEventListener('dragstart', blockDrag);
    document.addEventListener('keydown', blockKeys);
    document.addEventListener('keyup', onKeyUp);
    window.addEventListener('blur', hide);
    window.addEventListener('focus', show);
    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      document.removeEventListener('contextmenu', blockMenu);
      document.removeEventListener('copy', blockClipboard);
      document.removeEventListener('cut', blockClipboard);
      document.removeEventListener('selectstart', blockSelect);
      document.removeEventListener('dragstart', blockDrag);
      document.removeEventListener('keydown', blockKeys);
      document.removeEventListener('keyup', onKeyUp);
      window.removeEventListener('blur', hide);
      window.removeEventListener('focus', show);
      document.removeEventListener('visibilitychange', onVisibility);
      if (flashTimerRef.current) window.clearTimeout(flashTimerRef.current);
      setHidden(false);
    };
  }, [enabled]);

  if (!enabled || !hidden) return null;

  return (
    <div
      className="fixed inset-0 bg-chalk flex flex-col items-center justify-center gap-6"
      style={{ zIndex: 2147483647 }}
      aria-hidden="true"
    >
      <img
        src="/hero/logo.png"
        alt="Critical Care Classes"
        className="max-w-[70vw] max-h-[30vh] object-contain opacity-90 select-none pointer-events-none"
        draggable={false}
      />
      <p className="text-slate/70 text-sm font-sans px-6 text-center">
        {SCREENSHOT_MSG}
      </p>
      {viewer?.email && (
        <p className="text-slate/40 font-mono text-xs px-6 text-center">
          {viewer.name} · {viewer.email}
        </p>
      )}
    </div>
  );
}
