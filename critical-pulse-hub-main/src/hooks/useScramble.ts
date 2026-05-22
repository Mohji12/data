import { useState, useEffect, useRef } from 'react';

const CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';

export function useScramble(text: string, trigger: boolean = true): string {
  const [display, setDisplay] = useState(text);
  const frameRef = useRef<number>();

  useEffect(() => {
    if (!trigger) {
      setDisplay(text);
      return;
    }

    const duration = 800;
    const interval = 40;
    const steps = Math.floor(duration / interval);
    let step = 0;

    const scramble = () => {
      step++;
      const progress = step / steps;
      const resolved = Math.floor(progress * text.length);

      const result = text
        .split('')
        .map((char, i) => {
          if (i < resolved) return char;
          if (char === ' ') return ' ';
          return CHARS[Math.floor(Math.random() * CHARS.length)];
        })
        .join('');

      setDisplay(result);

      if (step < steps) {
        frameRef.current = window.setTimeout(scramble, interval);
      } else {
        setDisplay(text);
      }
    };

    scramble();

    return () => {
      if (frameRef.current) clearTimeout(frameRef.current);
    };
  }, [text, trigger]);

  return display;
}
