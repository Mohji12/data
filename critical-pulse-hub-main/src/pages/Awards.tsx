import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';
import { awards } from '@/lib/mockData';
import { Award, Sparkles } from 'lucide-react';

export default function Awards() {
  return (
    <div className="min-h-screen bg-chalk-warm">
      <Navbar />
      <section className="pt-28 pb-20 px-5 sm:px-8 lg:px-12">
        <div className="max-w-[880px] mx-auto">
          <div className="flex items-center gap-3 mb-5">
            <span className="inline-flex items-center justify-center w-10 h-10 rounded-sm bg-mint/15 border border-mint/25 text-mint">
              <Award className="w-5 h-5" strokeWidth={1.75} />
            </span>
            <div className="font-mono text-[10px] sm:text-[11px] text-mint tracking-[0.2em] uppercase">
              Recognition
            </div>
          </div>

          <h1
            className="font-display font-black text-slate tracking-tight mb-4"
            style={{ fontSize: 'clamp(2.25rem, 5.5vw, 3.75rem)', lineHeight: 1.05 }}
          >
            Awards, honours
            <br />
            <span className="text-mint">&amp; scholarships</span>
          </h1>

          <p className="font-sans text-sm sm:text-base text-ink-muted leading-relaxed max-w-2xl mb-14 border-l-2 border-mint/40 pl-5 py-1">
            A chronicle of national conferences, editorial leadership, society roles, and honours in
            critical care and respiratory medicine—aligned with Dr. Harish&apos;s academic and clinical
            journey.
          </p>

          <div className="relative">
            <div
              className="absolute left-[1.125rem] sm:left-6 top-2 bottom-2 w-px bg-gradient-to-b from-mint/50 via-border-soft to-mint/20"
              aria-hidden
            />

            <ul className="space-y-0 list-none m-0 p-0">
              {awards.map((item, i) => (
                <li
                  key={`${item.year}-${i}`}
                  className="relative pl-12 sm:pl-16 pb-12 sm:pb-14 last:pb-0 group"
                >
                  <div
                    className="absolute left-0 sm:left-1 top-1.5 w-9 h-9 sm:w-10 sm:h-10 rounded-full border-2 border-chalk-warm bg-chalk shadow-sm flex items-center justify-center ring-1 ring-border-soft group-hover:ring-mint/35 group-hover:bg-mint-pale transition-all duration-300"
                    aria-hidden
                  >
                    <Sparkles
                      className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-mint opacity-80 group-hover:opacity-100"
                      strokeWidth={1.5}
                    />
                  </div>

                  <div className="bg-chalk border border-border-soft rounded-sm p-5 sm:p-7 shadow-sm hover:border-mint/25 hover:shadow-md transition-all duration-300">
                    <time
                      className="font-mono text-xs sm:text-sm font-bold text-mint tracking-[0.12em] uppercase block mb-3"
                      dateTime={item.year === '—' ? undefined : item.year}
                    >
                      {item.year === '—' ? 'Recognition' : item.year}
                    </time>
                    <p className="font-sans text-[15px] sm:text-base text-slate/95 leading-[1.65] m-0">
                      {item.detail}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>
      <Footer />
    </div>
  );
}
