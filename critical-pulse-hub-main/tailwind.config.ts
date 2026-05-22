import type { Config } from "tailwindcss";

export default {
  darkMode: ["class"],
  content: ["./pages/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./app/**/*.{ts,tsx}", "./src/**/*.{ts,tsx}"],
  prefix: "",
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    borderRadius: {
      none: '0px',
      sm: '3px',
      DEFAULT: '6px',
      md: '10px',
      lg: '16px',
      xl: '24px',
      full: '9999px',
    },
    extend: {
      fontFamily: {
        display: ['"Times New Roman"', 'Times', 'serif'],
        sans: ['"Times New Roman"', 'Times', 'serif'],
        mono: ['"Times New Roman"', 'Times', 'serif'],
      },
      colors: {
        slate: {
          DEFAULT: '#1A2332',
          light: '#243041',
          dark: '#0F1520',
          50: '#F0F2F5',
          100: '#D6DBE4',
          200: '#525F7A',
          400: '#3D4F66',
          600: '#1A2332',
        },
        mint: {
          DEFAULT: '#04A87E',
          light: '#2EE8B5',
          dark: '#04A87E',
          pale: '#E6FBF5',
          glow: 'rgba(6,214,160,0.15)',
        },
        amber: {
          DEFAULT: '#B45309',
          light: '#FBC02D',
          pale: '#FEF8E7',
          glow: 'rgba(245,158,11,0.15)',
        },
        blush: {
          DEFAULT: '#FF6B8A',
          pale: '#FFF0F3',
          glow: 'rgba(255,107,138,0.12)',
        },
        cherry: {
          DEFAULT: '#DC2626',
          light: '#EF4444',
          dark: '#B91C1C',
        },
        chalk: {
          DEFAULT: '#FEFEFE',
          warm: '#F9F7F4',
          stone: '#F2EEE8',
          cool: '#F4F6FA',
          paper: '#FFFFFF',
        },
        ink: {
          DEFAULT: '#1A2332',
          secondary: '#1A2332',
          muted: '#2D3748',
          faint: '#4A5568',
          ghost: 'rgba(26,35,50,0.15)',
        },
        border: {
          DEFAULT: '#D1D5DB',
          soft: '#E5E7EB',
          strong: '#9CA3AF',
          slate: 'rgba(26,35,50,0.25)',
        },
        monitor: {
          bg: '#111927',
          card: '#1A2535',
          glow: 'rgba(6,214,160,0.08)',
          line: 'rgba(6,214,160,0.20)',
        },
        // Keep shadcn tokens working
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        sidebar: {
          DEFAULT: "hsl(var(--sidebar-background))",
          foreground: "hsl(var(--sidebar-foreground))",
          primary: "hsl(var(--sidebar-primary))",
          "primary-foreground": "hsl(var(--sidebar-primary-foreground))",
          accent: "hsl(var(--sidebar-accent))",
          "accent-foreground": "hsl(var(--sidebar-accent-foreground))",
          border: "hsl(var(--sidebar-border))",
          ring: "hsl(var(--sidebar-ring))",
        },
      },
      boxShadow: {
        xs: '0 1px 3px rgba(26,35,50,0.06)',
        sm: '0 2px 10px rgba(26,35,50,0.08)',
        md: '0 6px 24px rgba(26,35,50,0.10)',
        lg: '0 16px 48px rgba(26,35,50,0.10)',
        xl: '0 32px 80px rgba(26,35,50,0.12)',
        mint: '0 8px 40px rgba(6,214,160,0.20)',
        monitor: '0 0 0 1px rgba(6,214,160,0.15), 0 8px 32px rgba(0,0,0,0.4)',
        card: '0 0 0 1px rgba(26,35,50,0.06), 0 4px 20px rgba(26,35,50,0.07)',
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
} satisfies Config;
