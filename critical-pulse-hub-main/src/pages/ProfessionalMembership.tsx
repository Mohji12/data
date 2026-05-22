import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';
import { Link } from 'react-router-dom';
import { professionalSocietyMemberships } from '@/lib/mockData';
import { BadgeCheck, Globe2, Users } from 'lucide-react';

function parseMembership(line: string): { name: string; abbrev: string } {
  const m = line.match(/^(.*)\s+\(([^)]+)\)\s*$/);
  if (m) return { name: m[1].trim(), abbrev: m[2].trim() };
  return { name: line, abbrev: '—' };
}

export default function ProfessionalMembership() {
  const items = professionalSocietyMemberships.map(parseMembership);

  return (
    <div className="min-h-screen bg-chalk-warm">
      <Navbar />

      <section className="bg-monitor-bg scanline clip-bottom pt-28 pb-14 sm:pt-32 sm:pb-16 px-5 sm:px-8 lg:px-12">
        <div className="max-w-[1000px] mx-auto">
          <div className="flex items-center gap-3 mb-5">
            <span className="inline-flex items-center justify-center w-11 h-11 rounded-sm bg-mint/15 border border-mint/30 text-mint">
              <Users className="w-5 h-5" strokeWidth={1.75} />
            </span>
            <span className="font-mono text-[10px] sm:text-[11px] text-mint tracking-[0.22em] uppercase">
              Affiliations
            </span>
          </div>
          <h1
            className="font-display font-black text-chalk leading-[1.05] mb-4"
            style={{ fontSize: 'clamp(2rem, 5.5vw, 3.5rem)' }}
          >
            Professional
            <br />
            <span className="text-mint">membership</span>
          </h1>
          <p className="font-sans text-chalk/65 text-sm sm:text-base max-w-2xl leading-relaxed">
            National and international societies in critical care, anaesthesia, chest medicine, and clinical
            nutrition—supporting standards, research, and continuing professional development.
          </p>
        </div>
      </section>

      <section className="bg-chalk-warm py-14 sm:py-20 px-5 sm:px-8 lg:px-12 clip-top -mt-px">
        <div className="max-w-[1000px] mx-auto">
          <div className="flex flex-wrap items-end justify-between gap-6 mb-10 sm:mb-12">
            <div>
              <h2 className="font-display font-black text-slate text-2xl sm:text-3xl tracking-tight mb-2">
                Society memberships
              </h2>
              <p className="font-sans text-sm text-ink-muted max-w-xl m-0 leading-relaxed">
                Dr. Harish maintains active engagement with the bodies below—spanning regulatory registration,
                intensive care, regional and global critical care networks, and nutritional support in the acutely
                ill.
              </p>
            </div>
            <div className="flex items-center gap-2 font-mono text-[11px] text-ink-faint uppercase tracking-wider">
              <Globe2 className="w-4 h-4 text-mint" strokeWidth={1.5} />
              {items.length} organisations
            </div>
          </div>

          <ul className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-5 list-none m-0 p-0">
            {items.map(({ name, abbrev }) => (
              <li
                key={abbrev + name}
                className="group relative bg-chalk border border-border-soft rounded-sm p-6 sm:p-7 shadow-xs hover:border-mint/35 hover:shadow-md transition-all duration-300 overflow-hidden"
              >
                <div
                  className="absolute top-0 right-0 w-24 h-24 bg-mint/5 rounded-full -translate-y-1/2 translate-x-1/3 pointer-events-none group-hover:bg-mint/10 transition-colors"
                  aria-hidden
                />
                <div className="flex items-start gap-4 relative">
                  <span className="font-display font-black text-2xl sm:text-3xl text-mint/90 tabular-nums shrink-0 min-w-[3.5rem] sm:min-w-[4rem]">
                    {abbrev}
                  </span>
                  <div className="min-w-0 pt-0.5">
                    <div className="flex items-center gap-2 mb-2">
                      <BadgeCheck className="w-4 h-4 text-mint shrink-0 opacity-80" strokeWidth={1.75} />
                      <span className="font-mono text-[10px] text-ink-faint uppercase tracking-wider">
                        Member
                      </span>
                    </div>
                    <p className="font-sans text-[15px] sm:text-base font-medium text-slate leading-snug m-0">
                      {name}
                    </p>
                  </div>
                </div>
              </li>
            ))}
          </ul>

          <div className="mt-14 sm:mt-16 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-6 border-t border-border-soft pt-10">
            <p className="font-sans text-sm text-ink-muted m-0 max-w-md leading-relaxed">
              For full credentials, training, publications, and editorial roles, see the Faculty page.
            </p>
            <Link
              to="/faculty"
              className="magnetic inline-flex items-center justify-center bg-slate text-chalk rounded-sm px-8 py-3.5 font-sans font-semibold text-sm hover:bg-slate-light transition-colors shrink-0"
            >
              View faculty profile →
            </Link>
          </div>
        </div>
      </section>

      <Footer />
    </div>
  );
}
