import { getResolvedApiBaseForDisplay } from '@/lib/apiBase';

/** Small dev-only label so you can confirm which API the app is using. */
export default function DevApiIndicator() {
  if (!import.meta.env.DEV) return null;
  return (
    <div
      className="fixed bottom-2 right-2 z-[9999] max-w-[min(90vw,22rem)] rounded bg-ink/90 px-2 py-1 font-mono text-[10px] text-white shadow-lg"
      title="Remove by setting VITE_API_USE_PROXY=false in .env.development"
    >
      API: {getResolvedApiBaseForDisplay()}
    </div>
  );
}
