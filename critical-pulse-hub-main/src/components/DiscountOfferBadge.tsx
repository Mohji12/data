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
  batch_start?: string | null;
  headline?: string;
  batch_label?: string;
  cta_prefix?: string;
  valid_prefix?: string;
  /** Course description uses 3-line copy layout */
  layout?: 'default' | 'course';
};

/** Client fallback when API is unavailable (keeps badge visible). */
const FALLBACK: PromoBadgeConfig = {
  active: true,
  discount_pct: 25,
  description: 'DISCOUNT',
  valid_till: '2026-09-30',
  batch_start: '2026-10-01',
  days_left: 0,
  headline: 'OFFER',
  batch_label: 'NEW BATCHES START FROM',
  cta_prefix: 'REGISTER NOW TO AVAIL',
  valid_prefix: 'OFFER VALID TILL',
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

/** e.g. 1st OCTOBER / 30th SEPTEMBER — matches marketing art */
function formatOrdinalMonth(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(`${iso.slice(0, 10)}T12:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  const day = d.getDate();
  const suffix =
    day % 10 === 1 && day !== 11
      ? 'st'
      : day % 10 === 2 && day !== 12
        ? 'nd'
        : day % 10 === 3 && day !== 13
          ? 'rd'
          : 'th';
  const month = d.toLocaleDateString('en-GB', { month: 'long' }).toUpperCase();
  return `${day}${suffix} ${month}`;
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
  compact?: boolean;
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
  const rawDesc = (resolved.description || 'DISCOUNT').trim();
  const description =
    rawDesc.length <= 16 && !/batch/i.test(rawDesc) ? rawDesc.toUpperCase() : 'DISCOUNT';
  const headline = (resolved.headline || 'OFFER').trim().toUpperCase() || 'OFFER';
  const batchLabel =
    (resolved.batch_label || 'NEW BATCHES START FROM').trim().toUpperCase() ||
    'NEW BATCHES START FROM';
  const ctaPrefix =
    (resolved.cta_prefix || 'REGISTER NOW TO AVAIL').trim().toUpperCase() ||
    'REGISTER NOW TO AVAIL';
  const validPrefix =
    (resolved.valid_prefix || 'OFFER VALID TILL').trim().toUpperCase() || 'OFFER VALID TILL';
  const daysLeft = resolved.days_left;
  const showDaysLeft = Boolean(resolved.valid_till) && daysLeft > 0;
  const isCourseLayout = resolved.layout === 'course';
  const batchStartLabel = isCourseLayout
    ? formatDateLabel(resolved.batch_start)
    : formatOrdinalMonth(resolved.batch_start);
  const validTillLabel = formatOrdinalMonth(resolved.valid_till);
  const daysWord = daysLeft === 1 ? 'Day' : 'Days';

  const widthClass = isCourseLayout
    ? compact
      ? 'w-[240px] sm:w-[270px] lg:w-[300px]'
      : 'w-[260px] sm:w-[300px]'
    : compact
      ? 'w-[270px] sm:w-[300px] lg:w-[320px]'
      : 'w-[280px] sm:w-[310px] lg:w-[340px]';

  const aria = isCourseLayout
    ? `${discountPct}% Discount Available Now. Last ${daysLeft} ${daysWord} to Avail ${discountPct}% Discount.${
        batchStartLabel ? ` New Batch Starts From ${batchStartLabel}.` : ''
      }`
    : `${headline}. ${discountPct}% ${description}. ${
        batchStartLabel ? `${batchLabel} ${batchStartLabel}. ` : ''
      }${ctaPrefix} ${discountPct}% ${description}.${
        validTillLabel ? ` ${validPrefix} ${validTillLabel}.` : ''
      }`;

  return (
    <motion.div
      className={`relative overflow-visible ${className}`}
      initial={{ opacity: 0, scale: 0.88, y: 8, rotate: -10 }}
      animate={{ opacity: 1, scale: 1, y: 0, rotate: -10 }}
      transition={{ delay: 0.4, type: 'spring', stiffness: 260, damping: 22 }}
    >
      <motion.div
        className="overflow-visible"
        animate={{ y: [0, -4, 0] }}
        transition={{ duration: 4.2, repeat: Infinity, ease: 'easeInOut' }}
      >
        <Link
          to="/register"
          aria-label={aria}
          className={`group relative block overflow-visible ${widthClass} focus:outline-none focus-visible:ring-2 focus-visible:ring-mint focus-visible:ring-offset-2 focus-visible:ring-offset-chalk-warm`}
        >
          <motion.span
            className="relative block overflow-visible transition-transform duration-300 group-hover:scale-[1.03]"
            whileHover={{ rotate: -1 }}
            whileTap={{ scale: 0.97 }}
          >
            <img
              src={`${BADGE_IMG}?v=6`}
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
              /* Keep all copy inside the white cloud body (not the lobes). */
              <span className="absolute inset-[22%_16%_20%_16%] flex flex-col items-center justify-center text-center pointer-events-none gap-[2px] sm:gap-[3px] overflow-hidden">
                <span className="flex items-center justify-center gap-1 max-w-full">
                  <span className="flex gap-px shrink-0" aria-hidden>
                    <span className="block w-[5px] h-[1.5px] bg-[#1e4a7a] rotate-[-28deg] rounded-full" />
                    <span className="block w-[5px] h-[1.5px] bg-[#1e4a7a] rotate-[-28deg] rounded-full" />
                    <span className="block w-[5px] h-[1.5px] bg-[#1e4a7a] rotate-[-28deg] rounded-full" />
                  </span>
                  <span className="font-sans font-black text-[7px] sm:text-[8px] lg:text-[9px] uppercase tracking-[0.16em] text-[#0f2744] leading-none truncate">
                    {headline}
                  </span>
                  <span className="flex gap-px shrink-0" aria-hidden>
                    <span className="block w-[5px] h-[1.5px] bg-[#1e4a7a] rotate-[28deg] rounded-full" />
                    <span className="block w-[5px] h-[1.5px] bg-[#1e4a7a] rotate-[28deg] rounded-full" />
                    <span className="block w-[5px] h-[1.5px] bg-[#1e4a7a] rotate-[28deg] rounded-full" />
                  </span>
                </span>

                <span className="flex items-baseline justify-center gap-1 leading-none max-w-full">
                  <span className="font-display font-black text-[#e11d48] tabular-nums text-[22px] sm:text-[26px] lg:text-[30px] [text-shadow:0_1px_0_#fff,0_1px_2px_rgba(15,39,68,0.2)]">
                    {discountPct}
                    <span className="text-[12px] sm:text-[14px] lg:text-[16px] align-super ml-px">%</span>
                  </span>
                  <span className="font-sans font-black uppercase text-[#0f2744] text-[9px] sm:text-[11px] lg:text-[12px] tracking-wide truncate max-w-[45%]">
                    {description}
                  </span>
                </span>

                <span className="relative w-[70%] h-px bg-[#1e4a7a]/65 my-px" aria-hidden>
                  <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[4px] h-[4px] rounded-full bg-[#1e4a7a]" />
                </span>

                {batchStartLabel ? (
                  <span className="flex flex-col items-center gap-[2px] w-full min-w-0">
                    <span className="font-sans font-black uppercase text-[#0f2744] text-[6px] sm:text-[7px] lg:text-[8px] tracking-[0.04em] leading-tight px-1 line-clamp-2">
                      {batchLabel}
                    </span>
                    <span className="inline-flex max-w-[90%] items-center justify-center rounded-full bg-[#e11d48] px-2.5 sm:px-3 py-[2px] sm:py-[3px] shadow-sm">
                      <span className="font-sans font-black uppercase text-white text-[7px] sm:text-[8px] lg:text-[9px] tracking-wide leading-none truncate">
                        {batchStartLabel}
                      </span>
                    </span>
                  </span>
                ) : null}

                <span className="w-[88%] max-w-full rounded-full bg-[#7ec8e8]/90 px-1.5 sm:px-2 py-[2px] sm:py-[3px] border border-[#5bb0d6]/50">
                  <span className="font-sans font-bold uppercase text-[5.5px] sm:text-[6.5px] lg:text-[7.5px] leading-tight tracking-[0.01em] block line-clamp-2">
                    <span className="text-[#0f2744]">{ctaPrefix} </span>
                    <span className="text-[#e11d48] font-black">
                      {discountPct}% {description}
                    </span>
                  </span>
                </span>

                {validTillLabel ? (
                  <span className="flex items-center gap-1 w-full justify-center min-w-0 px-0.5">
                    <span className="flex-1 max-w-[28px] h-px bg-[#1e4a7a]/45 shrink" aria-hidden />
                    <span className="font-sans font-bold uppercase text-[#0f2744] text-[5.5px] sm:text-[6.5px] lg:text-[7px] tracking-[0.03em] leading-tight text-center line-clamp-2">
                      {validPrefix} {validTillLabel}
                    </span>
                    <span className="flex-1 max-w-[28px] h-px bg-[#1e4a7a]/45 shrink" aria-hidden />
                  </span>
                ) : null}
              </span>
            )}
          </motion.span>
        </Link>
      </motion.div>
    </motion.div>
  );
}
