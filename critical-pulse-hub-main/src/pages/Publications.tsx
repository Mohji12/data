import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';
import { Link } from 'react-router-dom';
import { bookChaptersPublished, peerReviewedPublications, researchInProgress } from '@/lib/mockData';
import type { LucideIcon } from 'lucide-react';
import { BookMarked, FileText, FlaskConical, Library } from 'lucide-react';

function SectionIntro({
  icon: Icon,
  kicker,
  title,
  description,
  accent = 'mint',
}: {
  icon: LucideIcon;
  kicker: string;
  title: string;
  description: string;
  accent?: 'mint' | 'amber' | 'slate';
}) {
  const ring =
    accent === 'amber'
      ? 'bg-amber/12 border-amber/30 text-amber'
      : accent === 'slate'
        ? 'bg-slate/8 border-slate/20 text-slate'
        : 'bg-mint/12 border-mint/25 text-mint';
  const bar =
    accent === 'amber' ? 'border-amber/35' : accent === 'slate' ? 'border-slate/25' : 'border-mint/35';

  return (
    <div className="mb-10 sm:mb-12">
      <div className="flex items-center gap-3 mb-4">
        <span className={`inline-flex items-center justify-center w-10 h-10 rounded-sm border ${ring}`}>
          <Icon className="w-5 h-5" strokeWidth={1.75} />
        </span>
        <span className="font-mono text-[10px] sm:text-[11px] text-ink-muted tracking-[0.2em] uppercase">
          {kicker}
        </span>
      </div>
      <h2 className="font-display font-black text-slate text-3xl sm:text-4xl tracking-tight leading-[1.1] mb-3">
        {title}
      </h2>
      <p className={`font-sans text-sm sm:text-base text-ink-muted leading-relaxed max-w-3xl border-l-2 ${bar} pl-5`}>
        {description}
      </p>
    </div>
  );
}

function NumberedList({
  items,
  startAt = 1,
  variant = 'default',
}: {
  items: string[];
  startAt?: number;
  variant?: 'default' | 'chapter' | 'progress';
}) {
  return (
    <ol className="space-y-3 sm:space-y-4 list-none m-0 p-0">
      {items.map((text, i) => {
        const n = startAt + i;
        const base =
          variant === 'chapter'
            ? 'border-amber/15 bg-chalk hover:border-amber/25'
            : variant === 'progress'
              ? 'border-dashed border-mint/30 bg-mint-pale/40 hover:border-mint/45'
              : 'border-border-soft bg-chalk hover:border-mint/20';
        return (
          <li
            key={i}
            className={`relative flex gap-4 sm:gap-5 rounded-sm border p-4 sm:p-5 shadow-xs transition-all duration-300 ${base}`}
          >
            <span
              className={`font-display font-black text-xl sm:text-2xl tabular-nums shrink-0 w-10 sm:w-12 text-right ${
                variant === 'chapter' ? 'text-amber' : variant === 'progress' ? 'text-mint' : 'text-mint/90'
              }`}
              aria-hidden
            >
              {n}.
            </span>
            <p className="font-sans text-[14px] sm:text-[15px] text-slate/95 leading-[1.65] m-0 pt-0.5">{text}</p>
          </li>
        );
      })}
    </ol>
  );
}

export default function Publications() {
  const nPapers = peerReviewedPublications.length;
  const nChapters = bookChaptersPublished.length;
  const nWip = researchInProgress.length;

  return (
    <div className="min-h-screen bg-chalk-warm">
      <Navbar />

      <section className="bg-monitor-bg scanline clip-bottom pt-28 pb-14 sm:pt-32 sm:pb-16 px-5 sm:px-8 lg:px-12">
        <div className="max-w-[1100px] mx-auto">
          <div className="font-mono text-[10px] sm:text-[11px] text-mint mb-4 tracking-[0.22em] uppercase">
            Research output
          </div>
          <h1
            className="font-display font-black text-chalk leading-[1.05] mb-4"
            style={{ fontSize: 'clamp(2rem, 5.5vw, 3.75rem)' }}
          >
            Publications
          </h1>
          <p className="font-sans text-chalk/65 text-sm sm:text-base max-w-2xl leading-relaxed mb-10">
            Peer-reviewed journal work, textbook chapters, and active studies—spanning critical care transport,
            infection, COVID-19, ventilation, echocardiography, and education.
          </p>
          <div className="flex flex-wrap gap-3 sm:gap-4">
            <div className="bg-monitor-card/90 border border-monitor-line rounded-sm px-5 py-3 min-w-[140px]">
              <div className="font-display font-black text-2xl text-mint">{nPapers}</div>
              <div className="font-mono text-[10px] text-chalk/50 uppercase tracking-wider mt-1">Journal papers</div>
            </div>
            <div className="bg-monitor-card/90 border border-monitor-line rounded-sm px-5 py-3 min-w-[140px]">
              <div className="font-display font-black text-2xl text-chalk">{nChapters}</div>
              <div className="font-mono text-[10px] text-chalk/50 uppercase tracking-wider mt-1">Book chapters</div>
            </div>
            <div className="bg-monitor-card/90 border border-monitor-line rounded-sm px-5 py-3 min-w-[140px]">
              <div className="font-display font-black text-2xl text-amber-light">{nWip}</div>
              <div className="font-mono text-[10px] text-chalk/50 uppercase tracking-wider mt-1">In progress</div>
            </div>
          </div>
        </div>
      </section>

      <section className="bg-chalk-warm py-14 sm:py-20 px-5 sm:px-8 lg:px-12 clip-top -mt-px">
        <div className="max-w-[900px] mx-auto">
          <SectionIntro
            icon={FileText}
            kicker="Already published"
            title="Peer-reviewed articles & reviews"
            description="Indexed journal publications including prospective studies, reviews, and case reports in Indian J Crit Care Med, Lung India, Annals of Intensive Care, and allied journals."
          />
          <NumberedList items={peerReviewedPublications} startAt={1} variant="default" />
        </div>
      </section>

      <section className="bg-chalk border-y border-border-soft py-14 sm:py-20 px-5 sm:px-8 lg:px-12">
        <div className="max-w-[900px] mx-auto">
          <SectionIntro
            icon={Library}
            kicker="Already published"
            title="Book chapters"
            description="Contributions to ISCCM volumes, perioperative and respiratory critical care texts, decision-making compendia, and applied physiology references."
            accent="amber"
          />
          <NumberedList items={bookChaptersPublished} startAt={1} variant="chapter" />
        </div>
      </section>

      <section className="bg-chalk-stone py-14 sm:py-24 px-5 sm:px-8 lg:px-12">
        <div className="max-w-[900px] mx-auto">
          <SectionIntro
            icon={FlaskConical}
            kicker="Pipeline"
            title="Working on publications"
            description="Ongoing analyses, manuscripts in preparation, and clinical trials—including delirium, antimicrobial PK, HFNC, cytokine storm therapies, and antifungal surveillance."
            accent="slate"
          />
          <NumberedList items={researchInProgress} startAt={1} variant="progress" />

          <div className="mt-14 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-t border-border-soft pt-10">
            <div className="flex items-start gap-3 text-ink-muted">
              <BookMarked className="w-5 h-5 text-mint shrink-0 mt-0.5" strokeWidth={1.5} />
              <p className="font-sans text-sm leading-relaxed m-0 max-w-md">
                Conference presentations and society honours are listed on the Faculty and Awards pages.
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <Link
                to="/faculty"
                className="font-mono text-xs uppercase tracking-wider text-slate border border-border-strong rounded-sm px-5 py-2.5 hover:bg-chalk transition-colors"
              >
                Faculty →
              </Link>
              <Link
                to="/awards"
                className="font-mono text-xs uppercase tracking-wider text-mint border border-mint/40 rounded-sm px-5 py-2.5 hover:bg-mint/10 transition-colors"
              >
                Awards →
              </Link>
            </div>
          </div>
        </div>
      </section>

      <Footer />
    </div>
  );
}
