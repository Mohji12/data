import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { apiClient } from '@/lib/apiClient';

const BADGE_IMG = '/discount-promo-badge.png';

export type PromoBadgeConfig = {
  active: boolean;
  discount_pct: number;
  description: string;
  valid_till: string | null;
  days_left: number;
  /** ISO date — course page “New Batch Starts From …” */
  batch_start?: string | null;
  /** Course description uses 3-line copy layout */
  layout?: 'default' | 'course';
};

/** Client fallback when API is unavailable (keeps badge visible). */
const FALLBACK: PromoBadgeConfig = {
  active: true,
  discount_pct: 25,
  description: 'discount',
  valid_till: '2026-09-16',
  days_left: 0,
};

function daysLeftUntilIso(iso: string | null | undefined, nowMs = Date.now()): number {
  if (!iso) return 0;
  const deadline = new Date(`${iso.slice(0, 10)}T23:59:59.999+05:30`).getTime();
  const msLeft = deadline - nowMs;
  if (msLeft <= 0) return 0;
  return Math.ceil(msLeft / (24 * 60 * 60 * 1000));
}

function withComputedDays(cfg: PromoBadgeConfig): PromoBadgeConfig {
  const hasDeadline = Boolean(cfg.valid_till);
  const days_left = hasDeadline
    ? cfg.days_left > 0
      ? cfg.days_left
      : daysLeftUntilIso(cfg.valid_till)
    : 0;
  const pctOk = Number(cfg.discount_pct) > 0;
  const active = Boolean(cfg.active) && pctOk && (!hasDeadline || days_left > 0);
  return {
    ...cfg,
    days_left,
    active,
  };
}

function formatDateLabel(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(`${iso.slice(0, 10)}T12:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

function formatValidTillLabel(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(`${iso.slice(0, 10)}T12:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
}

/**
 * Permanent discount badge — glossy cloud art with admin-configured overlay.
 * Pass `config` to override site-wide promo (e.g. per-course package discount).
 */
export default function DiscountOfferBadge({
  className = '',
  compact = false,
  config,
}: {
  className?: string;
  /** Slightly smaller for fee / course description cards */
  compact?: boolean;
  /** When set, use this instead of GET /registration/promo-badge */
  config?: PromoBadgeConfig | null;
}) {
  const useOverride = config !== undefined;
  const { data, isLoading } = useQuery({
    queryKey: ['promoBadge'],
    queryFn: () => apiClient('/registration/promo-badge') as Promise<PromoBadgeConfig>,
    staleTime: 3 * 60_000,
    refetchOnWindowFocus: true,
    retry: 1,
    enabled: !useOverride,
  });

  const source: PromoBadgeConfig | null = useOverride
    ? config
    : data ?? (isLoading ? { ...FALLBACK, active: false } : FALLBACK);

  if (!useOverride && isLoading) return null;
  if (!source) return null;

  const resolved = withComputedDays(source);
  if (!resolved.active) return null;

  const discountPct = resolved.discount_pct;
  const description = resolved.description || 'discount';
  const daysLeft = resolved.days_left;
  const untilLabel = formatValidTillLabel(resolved.valid_till);
  const showDaysLeft = Boolean(resolved.valid_till) && daysLeft > 0;
  const isCourseLayout = resolved.layout === 'course';
  const batchStartLabel = formatDateLabel(resolved.batch_start);
  const daysWord = daysLeft === 1 ? 'Day' : 'Days';

  const widthClass = isCourseLayout
    ? compact
      ? 'w-[240px] sm:w-[270px] lg:w-[300px]'
      : 'w-[260px] sm:w-[300px]'
    : compact
      ? 'w-[210px] sm:w-[230px] lg:w-[250px]'
      : 'w-[200px] sm:w-[228px] lg:w-[252px]';

  const aria = isCourseLayout
    ? `${discountPct}% Discount Available Now. Last ${daysLeft} ${daysWord} to Avail ${discountPct}% Discount.${
        batchStartLabel ? ` New Batch Starts From ${batchStartLabel}.` : ''
      }`
    : `${discountPct}% ${description} — register before ${resolved.valid_till ?? 'deadline'}. ${daysLeft} days remaining.`;

  return (
    <motion.div
      className={`relative overflow-visible ${className}`}
      initial={{ opacity: 0, scale: 0.88, y: 8, rotate: -20 }}
      animate={{ opacity: 1, scale: 1, y: 0, rotate: -20 }}
      transition={{ delay: 0.4, type: 'spring', stiffness: 260, damping: 22 }}
    >
      <motion.div
        className="overflow-visible"
        animate={{ y: [0, -5, 0] }}
        transition={{ duration: 4.2, repeat: Infinity, ease: 'easeInOut' }}
      >
        <Link
          to="/register"
          aria-label={aria}
          className={`group relative block overflow-visible ${widthClass} focus:outline-none focus-visible:ring-2 focus-visible:ring-mint focus-visible:ring-offset-2 focus-visible:ring-offset-chalk-warm`}
        >
          <motion.span
            className="relative block overflow-visible transition-transform duration-300 group-hover:scale-[1.06]"
            whileHover={{ rotate: -2 }}
            whileTap={{ scale: 0.96 }}
          >
            <img
              src={`${BADGE_IMG}?v=4`}
              alt=""
              width={512}
              height={340}
              className="w-full h-auto select-none pointer-events-none drop-shadow-lg"
              draggable={false}
            />

            {isCourseLayout ? (
              <span className="absolute inset-[16%_12%_18%_12%] flex flex-col items-center justify-center text-center pointer-events-none gap-0.5 sm:gap-1 px-1">
                <span className="font-sans font-black text-[#0f2744] text-[10px] sm:text-[12px] leading-tight">
                  {discountPct}% Discount Available Now
                </span>
                {showDaysLeft ? (
                  <motion.span
                    key={daysLeft}
                    initial={{ opacity: 0.6 }}
                    animate={{ opacity: 1 }}
                    className="font-sans font-bold text-[#0369a1] text-[9px] sm:text-[11px] leading-snug"
                  >
                    Last {daysLeft} {daysWord} to Avail {discountPct}% Discount
                  </motion.span>
                ) : null}
                {batchStartLabel ? (
                  <span className="font-sans font-bold text-[#1e3a5f] text-[8px] sm:text-[10px] leading-snug">
                    New Batch Starts From {batchStartLabel}
                  </span>
                ) : null}
              </span>
            ) : (
              <span className="absolute inset-[18%_16%_22%_16%] flex flex-col items-center justify-center text-center pointer-events-none">
                <motion.span
                  className="font-mono font-black text-[8px] sm:text-[9px] uppercase tracking-[0.18em] text-[#0284c7] leading-none"
                  animate={{ opacity: [0.75, 1, 0.75] }}
                  transition={{ duration: 2.4, repeat: Infinity, ease: 'easeInOut' }}
                >
                  Offer
                </motion.span>

                <motion.span
                  className="leading-none mt-0.5 sm:mt-1 whitespace-nowrap"
                  animate={{ scale: [1, 1.06, 1] }}
                  transition={{ duration: 2.8, repeat: Infinity, ease: 'easeInOut' }}
                >
                  <span className="font-display font-black text-[#0f2744] tabular-nums text-[28px] sm:text-[34px] drop-shadow-sm">
                    {discountPct}
                  </span>
                  <span className="font-display font-black text-[#e11d48] text-[16px] sm:text-[20px] align-top ml-0.5">
                    %
                  </span>
                </motion.span>

                <span className="font-sans text-[11px] sm:text-[13px] font-black text-[#0f2744] leading-none mt-0.5 whitespace-nowrap max-w-full truncate px-1">
                  {description}
                </span>

                {untilLabel ? (
                  <span className="font-mono font-bold text-[7px] sm:text-[8px] uppercase tracking-[0.1em] text-[#1e3a5f] mt-1 leading-tight whitespace-nowrap">
                    before {untilLabel}
                  </span>
                ) : null}

                {showDaysLeft ? (
                  <motion.span
                    key={daysLeft}
                    initial={{ scale: 0.85, opacity: 0.4 }}
                    animate={{ scale: [1, 1.08, 1], opacity: 1 }}
                    transition={{
                      scale: { duration: 1.8, repeat: Infinity, ease: 'easeInOut' },
                      opacity: { duration: 0.25 },
                    }}
                    className="mt-1 font-mono font-black text-[8px] sm:text-[9px] uppercase tracking-[0.12em] text-[#0369a1] whitespace-nowrap"
                  >
                    {daysLeft}d left
                  </motion.span>
                ) : null}
              </span>
            )}
          </motion.span>
        </Link>
      </motion.div>
    </motion.div>
  );
}
