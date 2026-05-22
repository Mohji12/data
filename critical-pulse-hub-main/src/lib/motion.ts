import type { Variants } from 'framer-motion';

const expo = [0.16, 1, 0.3, 1] as [number, number, number, number];

export const wipeUp: Variants = {
  hidden: { clipPath: 'inset(100% 0% 0% 0%)', opacity: 0 },
  show: { clipPath: 'inset(0% 0% 0% 0%)', opacity: 1, transition: { duration: 0.8, ease: expo } },
};

export const wordReveal: Variants = {
  hidden: { y: '110%', opacity: 0 },
  show: { y: '0%', opacity: 1, transition: { duration: 0.55, ease: expo } },
};

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 30, filter: 'blur(6px)' },
  show: { opacity: 1, y: 0, filter: 'blur(0px)', transition: { duration: 0.7, ease: expo } },
};

export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { duration: 0.5, ease: expo } },
};

export const scaleIn: Variants = {
  hidden: { opacity: 0, scale: 0.90 },
  show: { opacity: 1, scale: 1, transition: { duration: 0.6, ease: expo } },
};

export const slideLeft: Variants = {
  hidden: { opacity: 0, x: 50 },
  show: { opacity: 1, x: 0, transition: { duration: 0.65, ease: expo } },
};

export const stagger = (d = 0.07): Variants => ({
  show: { transition: { staggerChildren: d } },
});
