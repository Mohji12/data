import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';
import { Link } from 'react-router-dom';
import { facultyProfile } from '@/lib/mockData';
import type { LucideIcon } from 'lucide-react';
import {
  Award,
  BookOpen,
  GraduationCap,
  HeartPulse,
  Mic2,
  Sparkles,
  Stethoscope,
  Users,
} from 'lucide-react';

function SectionHeader({
  icon: Icon,
  kicker,
  title,
  description,
}: {
  icon: LucideIcon;
  kicker: string;
  title: string;
  description?: string;
}) {
  return (
    <div className="mb-10 sm:mb-12">
      <div className="flex items-center gap-3 mb-4">
        <span className="inline-flex items-center justify-center w-10 h-10 rounded-sm bg-mint/12 border border-mint/25 text-mint">
          <Icon className="w-5 h-5" strokeWidth={1.75} />
        </span>
        <span className="font-mono text-[10px] sm:text-[11px] text-mint tracking-[0.2em] uppercase">{kicker}</span>
      </div>
      <h2 className="font-display font-black text-slate text-3xl sm:text-4xl lg:text-[2.75rem] tracking-tight leading-[1.1] mb-3">
        {title}
      </h2>
      {description ? (
        <p className="font-sans text-sm sm:text-base text-ink-muted leading-relaxed max-w-3xl border-l-2 border-mint/35 pl-5">
          {description}
        </p>
      ) : null}
    </div>
  );
}

export default function Faculty() {
  const { displayName, degrees, titles, highlights, expertise, memberships, training, presentations } =
    facultyProfile;

  return (
    <div className="min-h-screen bg-chalk-warm">
      <Navbar />

      <section className="bg-monitor-bg scanline clip-bottom pt-28 pb-16 sm:pt-32 sm:pb-20 px-5 sm:px-8 lg:px-12">
        <div className="max-w-[1200px] mx-auto">
          <div className="font-mono text-[10px] sm:text-[11px] text-mint mb-4 tracking-[0.2em] uppercase">
            Faculty credentials
          </div>
          <h1
            className="font-display font-black text-chalk leading-[1.05] mb-3"
            style={{ fontSize: 'clamp(2rem, 5vw, 3.5rem)' }}
          >
            {displayName}
          </h1>
        </div>
      </section>

      <section className="bg-chalk-warm py-16 sm:py-20 px-5 sm:px-8 lg:px-12 clip-top -mt-px">
        <div className="max-w-[1200px] mx-auto flex flex-col lg:flex-row gap-12 lg:gap-16">
          <div className="lg:w-[42%] shrink-0">
            <div className="relative sticky top-28">
              <img
                src="/WhatsApp%20Image%202026-02-23%20at%2023.27.04.jpeg"
                alt={displayName}
                className="img-doc w-full rounded-sm shadow-lg object-cover aspect-[3/4] border border-border-soft"
              />
              <div className="absolute bottom-4 left-4 right-4 sm:right-auto bg-monitor-card/95 backdrop-blur-sm border border-monitor-line rounded-sm p-4 sm:p-5 shadow-monitor max-w-sm">
                <div className="font-mono text-[10px] text-mint uppercase tracking-wider leading-snug">
                  India&apos;s first MCI-recognised DM in Critical Care Medicine
                </div>
                <div className="font-sans text-[12px] text-chalk/55 mt-2">European Diploma (EDIC) · Dublin</div>
              </div>
            </div>
          </div>

          <div className="lg:w-[58%] min-w-0">
            <div className="font-mono text-[10px] sm:text-[11px] text-mint tracking-[0.18em] mb-3 uppercase">
              Qualifications &amp; role
            </div>
            <p className="font-sans text-[15px] sm:text-base text-slate/95 leading-[1.7] mb-8 border-l-2 border-mint/30 pl-5">
              {degrees}
            </p>
            <div className="space-y-2 mb-10">
              {titles.map((line) => (
                <p key={line} className="font-display font-bold text-lg sm:text-xl text-slate leading-snug">
                  {line}
                </p>
              ))}
            </div>

            <SectionHeader
              icon={Award}
              kicker="Career highlights"
              title="Credentials at a glance"
              description="Leadership in critical care education, editorial roles, national guidelines, and recognition from peers and institutions."
            />
            <ul className="space-y-3.5 list-none m-0 p-0 mb-12">
              {highlights.map((item) => (
                <li key={item} className="flex gap-3.5 items-start">
                  <span className="font-mono text-mint text-sm mt-0.5 shrink-0" aria-hidden>
                    →
                  </span>
                  <span className="font-sans text-[15px] text-ink-secondary leading-relaxed">{item}</span>
                </li>
              ))}
            </ul>

            <Link
              to="/contact"
              className="magnetic inline-flex items-center gap-2 bg-slate text-chalk rounded-sm px-8 py-3.5 font-sans font-semibold text-sm hover:bg-slate-light transition-all border border-slate-dark/20"
            >
              Get in touch
              <span aria-hidden>→</span>
            </Link>
          </div>
        </div>
      </section>

      <section className="bg-chalk border-y border-border-soft py-16 sm:py-20 px-5 sm:px-8 lg:px-12">
        <div className="max-w-[1200px] mx-auto">
          <SectionHeader
            icon={Stethoscope}
            kicker="Clinical focus"
            title="Special interests & expertise"
            description="Areas of deep practice, teaching, and protocol development across infection, organ support, and ICU systems."
          />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-3">
            {expertise.map((item) => (
              <div
                key={item}
                className="group py-4 px-5 rounded-sm border border-transparent border-l-2 border-l-transparent hover:border-l-mint hover:bg-chalk-warm hover:border-border-soft transition-all duration-300"
              >
                <span className="font-sans text-[15px] text-slate/90 leading-snug group-hover:text-slate transition-colors">
                  {item}
                </span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-chalk-stone py-16 sm:py-20 px-5 sm:px-8 lg:px-12">
        <div className="max-w-[1200px] mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-14 lg:gap-16">
            <div>
              <SectionHeader
                icon={Users}
                kicker="Affiliations"
                title="Professional membership"
                description="Societies and councils reflecting commitment to standards in intensive care, anaesthesia, and nutrition."
              />
              <ul className="flex flex-wrap gap-2.5 list-none m-0 p-0">
                {memberships.map((m) => (
                  <li
                    key={m}
                    className="font-sans text-[13px] sm:text-sm text-slate/90 bg-chalk border border-border-soft rounded-sm px-4 py-2.5 hover:border-mint/30 hover:shadow-xs transition-all"
                  >
                    {m}
                  </li>
                ))}
              </ul>
              <Link
                to="/membership"
                className="inline-flex mt-6 font-mono text-[11px] uppercase tracking-wider text-mint border border-mint/35 rounded-sm px-4 py-2 hover:bg-mint/10 transition-colors"
              >
                Membership page →
              </Link>
            </div>
            <div>
              <SectionHeader
                icon={GraduationCap}
                kicker="Certifications"
                title="Special training"
              />
              <ul className="space-y-4 list-none m-0 p-0">
                {training.map((t) => (
                  <li
                    key={t}
                    className="flex gap-3 items-start font-sans text-[15px] text-ink-secondary leading-relaxed bg-chalk border border-border-soft rounded-sm p-4 sm:p-5"
                  >
                    <HeartPulse className="w-5 h-5 text-mint shrink-0 mt-0.5" strokeWidth={1.5} aria-hidden />
                    {t}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      <section className="bg-chalk-warm py-16 sm:py-24 px-5 sm:px-8 lg:px-12">
        <div className="max-w-[900px] mx-auto">
          <SectionHeader
            icon={Mic2}
            kicker="Academic platform"
            title="Presentations"
            description="Selected national and international conference presentations and posters."
          />

          <div className="relative">
            <div
              className="absolute left-[1.125rem] sm:left-6 top-2 bottom-2 w-px bg-gradient-to-b from-mint/45 via-border-strong/40 to-mint/15"
              aria-hidden
            />
            <ul className="space-y-0 list-none m-0 p-0">
              {presentations.map((item, i) => (
                <li key={`${item.year}-${i}`} className="relative pl-12 sm:pl-16 pb-10 sm:pb-12 last:pb-0 group">
                  <div
                    className="absolute left-0 sm:left-1 top-1.5 w-9 h-9 sm:w-10 sm:h-10 rounded-full border-2 border-chalk-warm bg-chalk shadow-sm flex items-center justify-center ring-1 ring-border-soft group-hover:ring-mint/35 group-hover:bg-mint-pale transition-all duration-300"
                    aria-hidden
                  >
                    <Sparkles className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-mint opacity-85" strokeWidth={1.5} />
                  </div>
                  <div className="bg-chalk border border-border-soft rounded-sm p-5 sm:p-6 shadow-sm hover:border-mint/25 hover:shadow-md transition-all">
                    <time className="font-mono text-xs sm:text-sm font-bold text-mint tracking-[0.12em] uppercase block mb-2">
                      {item.year}
                    </time>
                    <p className="font-sans text-[15px] sm:text-base text-slate/95 leading-[1.65] m-0">{item.detail}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>

          <div className="mt-14 flex flex-wrap items-center gap-4 justify-between border-t border-border-soft pt-10">
            <div className="flex items-center gap-3 text-ink-muted">
              <BookOpen className="w-5 h-5 text-mint shrink-0" strokeWidth={1.5} />
              <span className="font-sans text-sm leading-relaxed max-w-md">
                Full publication list, chapters, and ongoing research are on the Publications page; honours are on Awards.
              </span>
            </div>
            <div className="flex flex-wrap gap-3">
              <Link
                to="/publications"
                className="font-mono text-xs uppercase tracking-wider text-slate border border-border-strong rounded-sm px-5 py-2.5 hover:bg-chalk transition-colors"
              >
                Publications →
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
