type AppLoaderProps = {
  label?: string;
  /** Fill the parent area instead of a small inline block. */
  fullHeight?: boolean;
};

/** Branded loading indicator — app logo inside a spinning progress ring. */
export default function AppLoader({ label = 'Loading…', fullHeight = true }: AppLoaderProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={`flex flex-col items-center justify-center gap-5 ${fullHeight ? 'min-h-[320px] py-16' : 'py-8'}`}
    >
      <div className="relative w-20 h-20">
        <div className="absolute inset-0 rounded-full border-2 border-mint/15" aria-hidden />
        <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-mint animate-spin" aria-hidden />
        <img
          src="/hero/logo.png"
          alt="Critical Care Medicine"
          className="absolute inset-0 m-auto w-12 h-12 object-contain"
        />
      </div>
      <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-ink-faint">{label}</div>
    </div>
  );
}


