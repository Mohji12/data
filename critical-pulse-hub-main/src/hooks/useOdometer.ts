import { useState, useEffect, useRef } from 'react';

function easeOutExpo(t: number): number {
  return t === 1 ? 1 : 1 - Math.pow(2, -10 * t);
}

export function useOdometer(target: number, decimals: number = 0): string {
  const [value, setValue] = useState(0);
  const hasAnimated = useRef(false);

  useEffect(() => {
    // Re-run animation whenever target changes (e.g. API data arrives after initial 0)
    hasAnimated.current = false;
    setValue(0);

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !hasAnimated.current) {
          hasAnimated.current = true;
          const duration = 1800;
          const startTime = performance.now();

          const animate = (now: number) => {
            const elapsed = now - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const eased = easeOutExpo(progress);
            setValue(eased * target);

            if (progress < 1) {
              requestAnimationFrame(animate);
            } else {
              setValue(target);
            }
          };

          requestAnimationFrame(animate);
        }
      },
      { threshold: 0.1 }
    );

    // Observe a dummy element or use document
    const el = document.createElement('div');
    el.style.position = 'absolute';
    el.style.opacity = '0';
    el.style.pointerEvents = 'none';
    document.body.appendChild(el);
    observer.observe(el);

    // Auto-trigger after a small delay as fallback
    const timeout = setTimeout(() => {
      if (!hasAnimated.current) {
        hasAnimated.current = true;
        const duration = 1800;
        const startTime = performance.now();
        const animate = (now: number) => {
          const elapsed = now - startTime;
          const progress = Math.min(elapsed / duration, 1);
          const eased = easeOutExpo(progress);
          setValue(eased * target);
          if (progress < 1) requestAnimationFrame(animate);
          else setValue(target);
        };
        requestAnimationFrame(animate);
      }
    }, 300);

    return () => {
      observer.disconnect();
      el.remove();
      clearTimeout(timeout);
    };
  }, [target]);

  return decimals > 0 ? value.toFixed(decimals) : Math.round(value).toString();
}
