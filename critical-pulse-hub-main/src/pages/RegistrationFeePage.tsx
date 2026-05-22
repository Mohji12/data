import { Link } from 'react-router-dom';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';
import { apiClient } from '@/lib/apiClient';
import { resolvePublicUploadUrl } from '@/lib/apiBase';
import { toEmbeddableVideoUrl } from '@/lib/videoUrl';

export type FeeStructureBlock = {
  group_label: string;
  registration_fee: string[];
  discount: string[];
  total: string[];
  total_payable: string[];
  package_ids: number[];
  plan_badges: string[];
  column_headers?: string[];
};

export type FeeStructureResponse = {
  batch_slug: string;
  batch_name: string;
  page_title: string;
  breadcrumb_tail: string;
  notice: string | null;
  description: string | null;
  brochure_url: string | null;
  video_url: string | null;
  video_resolved_url: string | null;
  column_headers: string[];
  indian: FeeStructureBlock;
  foreign: FeeStructureBlock;
};

const rowLabels = ['Registration Fee', 'Discount', 'Total', 'Total Amount Payable'] as const;

function brochureKind(url?: string | null): 'pdf' | 'image' | 'other' {
  const value = String(url || '').toLowerCase();
  if (!value) return 'other';
  if (value.includes('.pdf')) return 'pdf';
  if (/\.(png|jpe?g|webp|gif)(\?|$)/i.test(value)) return 'image';
  return 'other';
}

function DynamicFeesTable({
  headers,
  indian,
  foreign,
  batchSlug,
}: {
  headers: string[];
  indian: FeeStructureBlock;
  foreign: FeeStructureBlock;
  batchSlug: string;
}) {
  const colSpanTop = 2 + headers.length;

  const renderBlock = (block: FeeStructureBlock) => {
    const rows = [block.registration_fee, block.discount, block.total, block.total_payable];
    return (
      <>
        {rowLabels.map((label, idx) => (
          <tr key={`${block.group_label}-${label}`}>
            {idx === 0 && (
              <td
                rowSpan={4}
                className="border border-slate/25 px-2 py-2.5 font-sans font-semibold text-slate align-middle bg-chalk-warm/50"
              >
                {block.group_label}
              </td>
            )}
            <td
              className={`border border-slate/25 px-2 py-2.5 font-sans text-ink-secondary ${
                label === 'Total Amount Payable' ? 'font-bold text-slate' : ''
              }`}
            >
              {label}
            </td>
            {rows[idx].map((cell, i) => (
              <td
                key={i}
                className={`border border-slate/25 px-2 py-2.5 font-sans tabular-nums text-ink ${
                  label === 'Total Amount Payable' ? 'font-bold text-slate' : ''
                }`}
              >
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </>
    );
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] border-collapse text-sm border border-slate/40">
        <thead>
          <tr className="bg-slate text-chalk">
            <th
              colSpan={colSpanTop}
              className="border border-slate px-3 py-3 font-sans font-bold text-center"
            >
              Registration Fees
            </th>
          </tr>
          <tr className="bg-slate text-chalk">
            <th
              colSpan={2}
              className="border border-slate/20 px-2 py-3 font-sans font-semibold text-center text-xs sm:text-sm"
            >
              Category
            </th>
            {headers.map((h) => (
              <th
                key={h}
                className="border border-slate/20 px-2 py-3 font-sans font-semibold text-center text-[10px] sm:text-[11px] leading-snug align-bottom"
              >
                {h}
              </th>
            ))}
          </tr>
          <tr className="bg-slate/95 text-chalk">
            <th colSpan={2} className="border border-slate/20 px-2 py-2 text-[10px] font-semibold uppercase tracking-wide text-center">
              Plan Type
            </th>
            {headers.map((_, i) => {
              const planBadge =
                (indian.plan_badges?.[i] && indian.plan_badges[i] !== '—')
                  ? indian.plan_badges[i]
                  : ((foreign.plan_badges?.[i] && foreign.plan_badges[i] !== '—') ? foreign.plan_badges[i] : '—');
              return (
                <th key={`plan-${i}`} className="border border-slate/20 px-2 py-2 text-center">
                  <span className="inline-flex items-center justify-center rounded-sm border border-white/30 bg-white/10 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide">
                    {planBadge}
                  </span>
                </th>
              );
            })}
          </tr>
          <tr className="bg-slate/95 text-chalk">
            <th colSpan={2} className="border border-slate/20 px-2 py-2" />
            {headers.map((_, i) => {
              const indianPackageId = indian.package_ids?.[i] || 0;
              return (
                <th key={`apply-${i}`} className="border border-slate/20 px-2 py-2 text-center">
                  {indianPackageId > 0 ? (
                    <Link
                      to={`/register?batch=${encodeURIComponent(batchSlug)}&package_id=${indianPackageId}&country_id=101`}
                      className="inline-flex items-center justify-center rounded-sm bg-mint text-slate px-2.5 py-1 text-[10px] font-bold hover:bg-mint-light transition-colors"
                    >
                      Apply (Indian)
                    </Link>
                  ) : (
                    <span className="text-[10px] text-white/50">—</span>
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody className="bg-chalk text-center">
          {renderBlock(indian)}
          <tr className="bg-slate text-chalk">
            <th
              colSpan={2}
              className="border border-slate/20 px-2 py-3 font-sans font-semibold text-center text-xs sm:text-sm"
            >
              Category
            </th>
            {headers.map((_, i) => {
              const foreignPackageId = foreign.package_ids?.[i] || 0;
              const foreignHeader = foreign.column_headers?.[i] || '';
              return (
                <th
                  key={`fh-${i}`}
                  className="border border-slate/20 px-2 py-3 font-sans font-semibold text-center text-[10px] sm:text-[11px] leading-snug align-bottom"
                >
                  {foreignPackageId > 0 ? foreignHeader : ''}
                </th>
              );
            })}
          </tr>
          <tr className="bg-slate/95 text-chalk">
            <th colSpan={2} className="border border-slate/20 px-2 py-2 text-[10px] font-semibold uppercase tracking-wide text-center">
              Plan Type
            </th>
            {headers.map((_, i) => {
              const foreignPackageId = foreign.package_ids?.[i] || 0;
              const foreignBadge = foreign.plan_badges?.[i];
              const hasForeignBadge = !!(foreignBadge && foreignBadge !== '—');
              return (
                <th key={`fplan-${i}`} className="border border-slate/20 px-2 py-2 text-center">
                  {foreignPackageId > 0 && hasForeignBadge ? (
                    <span className="inline-flex items-center justify-center rounded-sm border border-white/30 bg-white/10 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wide">
                      {foreignBadge}
                    </span>
                  ) : null}
                </th>
              );
            })}
          </tr>
          <tr className="bg-slate/95 text-chalk">
            <th colSpan={2} className="border border-slate/20 px-2 py-2" />
            {headers.map((_, i) => {
              const foreignPackageId = foreign.package_ids?.[i] || 0;
              const foreignOffer = foreign.column_headers?.[i] || '';
              return (
                <th key={`fapply-${i}`} className="border border-slate/20 px-2 py-2 text-center">
                  {foreignPackageId > 0 ? (
                    <Link
                      to={`/register?batch=${encodeURIComponent(batchSlug)}&package_id=${foreignPackageId}&foreign=1&offer=${encodeURIComponent(foreignOffer)}`}
                      className="inline-flex items-center justify-center rounded-sm bg-mint text-slate px-2.5 py-1 text-[10px] font-bold hover:bg-mint-light transition-colors"
                    >
                      Apply (Foreign)
                    </Link>
                  ) : (
                    <span className="text-[10px] text-white/50">—</span>
                  )}
                </th>
              );
            })}
          </tr>
          {renderBlock(foreign)}
        </tbody>
      </table>
    </div>
  );
}

type Props = { batchSlug?: string };

export default function RegistrationFeePage({ batchSlug }: Props) {
  const params = useParams();
  const resolvedBatchSlug = (batchSlug || params.batchSlug || '').trim();
  const { data, isLoading, error } = useQuery<FeeStructureResponse>({
    queryKey: ['feeStructure', resolvedBatchSlug],
    enabled: !!resolvedBatchSlug,
    queryFn: () =>
      apiClient(`/registration/fee-structure?batch_slug=${encodeURIComponent(resolvedBatchSlug)}`),
  });
  const brochureResolvedUrl = resolvePublicUploadUrl(data?.brochure_url);
  const brochureType = brochureKind(brochureResolvedUrl);

  return (
    <div className="min-h-screen bg-chalk-warm flex flex-col">
      <Navbar />

      <section className="bg-gradient-to-br from-[#0d9488] to-[#0e7490] px-4 pt-10 pb-14 text-center">
        <h1
          className="font-display font-black text-chalk tracking-tight px-2"
          style={{ fontSize: 'clamp(26px, 4.5vw, 42px)' }}
        >
          {isLoading ? 'Loading…' : data?.page_title ?? 'Registration'}
        </h1>
        <nav className="mt-3 font-sans text-sm text-white/90 px-2 max-w-3xl mx-auto leading-relaxed" aria-label="Breadcrumb">
          <Link to="/" className="hover:text-white transition-colors">
            Home
          </Link>
          <span className="mx-2 text-cyan-200/90">•</span>
          <span>{data?.breadcrumb_tail ?? resolvedBatchSlug}</span>
        </nav>
      </section>

      <main className="flex-1 w-full max-w-[960px] mx-auto px-4 sm:px-6 -mt-8 pb-16 relative z-10">
        <div className="bg-chalk border border-border-soft rounded-sm shadow-[0_12px_40px_rgba(26,35,50,0.08)] p-6 sm:p-10">
          <h2 className="font-display font-bold text-2xl sm:text-3xl text-slate mb-6 text-center">
            Registration Fee Structure
          </h2>

          {error && (
            <p className="text-center text-red-600 font-sans text-sm mb-6">
              {error instanceof Error ? error.message : 'Could not load fee structure.'}
            </p>
          )}

          {data?.notice ? (
            <p className="font-sans text-sm sm:text-[15px] text-red-600 leading-relaxed mb-8 text-center whitespace-pre-line">
              {data.notice}
            </p>
          ) : null}

          {isLoading && !data && (
            <div className="py-16 text-center font-mono text-sm text-ink-faint animate-pulse">Loading fee table…</div>
          )}
          
          {data?.description && (
            <div className="mb-8 prose prose-slate max-w-none">
              <p className="font-sans text-base text-slate-light whitespace-pre-line leading-relaxed">
                {data.description}
              </p>
            </div>
          )}

          {data?.brochure_url && brochureResolvedUrl && (
            <div className="mb-8 space-y-4">
              <div className="flex justify-center">
                <a
                  href={brochureResolvedUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center justify-center rounded-sm bg-slate text-chalk px-6 py-3 font-sans font-semibold text-sm hover:bg-slate-light transition-colors"
                >
                  View Brochure
                </a>
              </div>
              {brochureType === 'pdf' && (
                <div className="w-full h-[560px] overflow-hidden rounded-sm border border-border-soft bg-chalk">
                  <iframe
                    src={brochureResolvedUrl}
                    title="Batch Brochure"
                    className="w-full h-full border-0"
                  />
                </div>
              )}
              {brochureType === 'image' && (
                <div className="w-full overflow-hidden rounded-sm border border-border-soft bg-chalk">
                  <img
                    src={brochureResolvedUrl}
                    alt="Batch brochure preview"
                    className="w-full h-auto object-contain"
                  />
                </div>
              )}
            </div>
          )}

          {(data?.video_url || data?.video_resolved_url) && (
            <div className="mb-10 aspect-video w-full overflow-hidden rounded-sm bg-black shadow-lg">
              {data.video_resolved_url ? (
                <video 
                  src={resolvePublicUploadUrl(data.video_resolved_url)} 
                  controls 
                  className="w-full h-full"
                />
              ) : (
                <iframe
                  src={toEmbeddableVideoUrl(data.video_url)}
                  title="Batch Preview Video"
                  className="w-full h-full border-0"
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                  allowFullScreen
                />
              )}
            </div>
          )}

          {data && (
            <DynamicFeesTable headers={data.column_headers} indian={data.indian} foreign={data.foreign} batchSlug={resolvedBatchSlug} />
          )}

          <div className="mt-10 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pt-8 border-t border-border-soft">
            <p className="font-sans text-xs text-ink-muted max-w-md text-center sm:text-left">
              Amounts come from the current packages in the database. Select the matching tier when you register
              according to the date of payment.
            </p>
            <Link
              to={`/register?batch=${encodeURIComponent(resolvedBatchSlug)}`}
              className="magnetic inline-flex items-center justify-center rounded-sm bg-mint text-slate px-10 py-3.5 font-sans font-bold text-[15px] shadow-sm hover:bg-mint-light transition-colors text-center shrink-0"
            >
              Apply →
            </Link>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
