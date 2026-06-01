import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';
import { Link } from 'react-router-dom';
import { ArrowUpRight, FileText } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/apiClient';
import { resolvePublicUploadUrl } from '@/lib/apiBase';
import { filterRegistrationCatalogBatches } from '@/lib/publicBatches';

type CatalogRow = {
  batch_slug: string;
  batch_name: string;
  launch_ready: boolean;
  status: string;
  brochure_url?: string | null;
  description?: string | null;
};

export default function Membership() {
  const { data: catalog, isLoading, error } = useQuery({
    queryKey: ['registrationCatalogCoursesPage'],
    queryFn: () => apiClient('/registration/catalog?include_inactive=true') as Promise<CatalogRow[]>,
  });

  const rows = [...filterRegistrationCatalogBatches(catalog || [])].sort((a, b) =>
    a.batch_name.localeCompare(b.batch_name),
  );

  return (
    <div className="min-h-screen">
      <Navbar />
      <section className="bg-monitor-bg scanline clip-bottom pt-32 pb-24 px-6 lg:px-12">
        <div className="max-w-[1400px] mx-auto">
          <div className="font-mono text-[11px] text-mint mb-4 tracking-[0.16em] uppercase">PROGRAMMES</div>
          <h1 className="font-display font-black text-6xl text-chalk">COURSES.</h1>
          <p className="font-sans text-sm text-chalk/70 mt-4 max-w-2xl">
            Open a batch brochure (PDF) uploaded from admin, or register when the batch is launch-ready.
          </p>
        </div>
      </section>
      <section className="bg-chalk-warm py-24 px-6 lg:px-12 clip-top">
        <div className="max-w-[1400px] mx-auto">
          {isLoading && <div className="font-mono text-xs text-ink-faint animate-pulse">Loading programmes…</div>}
          {error && <div className="text-red-600 font-sans text-sm">Could not load course list.</div>}
          {!isLoading && !error && rows.length === 0 && (
            <p className="font-sans text-sm text-ink-muted">No batches configured yet.</p>
          )}
          <div className="space-y-4">
            {rows.map((c, i) => {
              const pdfHref = resolvePublicUploadUrl(c.brochure_url);
              return (
                <div
                  key={c.batch_slug}
                  className="bg-chalk border border-border-soft rounded-sm p-8 hover:border-mint/30 hover:shadow-sm transition-all group"
                >
                  <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                    <div className="flex items-center gap-6">
                      <span className="font-mono text-xs text-ink-faint group-hover:text-mint transition-colors">
                        {String(i + 1).padStart(2, '0')}
                      </span>
                      <div>
                        <div className="font-display font-bold text-2xl text-slate">{c.batch_name}</div>
                        <div className="font-mono text-[11px] text-ink-faint mt-1 flex flex-wrap gap-2 items-center">
                          <span>{c.status === '1' ? 'Active' : 'Inactive'}</span>
                          <span>·</span>
                          <span>{c.launch_ready ? 'Registration open' : 'Registration not ready'}</span>
                        </div>
                        {c.description && (
                          <p className="font-sans text-[13px] text-ink-secondary mt-3 max-w-xl line-clamp-3">
                            {c.description}
                          </p>
                        )}
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-3 ml-10 lg:ml-0">
                      {pdfHref ? (
                        <a
                          href={pdfHref}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-2 border border-mint/40 text-mint rounded-sm px-5 py-3 font-sans text-sm font-semibold hover:bg-mint/10 transition-all"
                        >
                          <FileText size={16} />
                          Brochure PDF
                        </a>
                      ) : (
                        <span className="font-mono text-[11px] text-ink-faint px-2">No brochure uploaded</span>
                      )}
                      {c.launch_ready ? (
                        <Link
                          to={`/register/${encodeURIComponent(c.batch_slug)}`}
                          className="magnetic bg-slate text-chalk rounded-sm px-6 py-3 font-sans font-semibold text-sm hover:bg-slate-light transition-all flex items-center gap-2"
                        >
                          Register <ArrowUpRight size={14} />
                        </Link>
                      ) : (
                        <Link
                          to="/register"
                          className="font-sans text-sm text-ink-muted border border-border-soft rounded-sm px-5 py-3 hover:bg-chalk-cool transition-all"
                        >
                          Browse registration
                        </Link>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>
      <Footer />
    </div>
  );
}
