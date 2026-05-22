import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { Stethoscope, Activity, BookOpen, GraduationCap, Award, Heart, MonitorCheck, Brain, Video, ClipboardCheck, MessageCircle, BarChart3, Users, Shield, PlayCircle, ArrowUpRight, Quote } from 'lucide-react';
import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';
import ECGWaveform from '@/components/ECGWaveform';
import { useScramble } from '@/hooks/useScramble';
import { useOdometer } from '@/hooks/useOdometer';
import { useInView } from '@/hooks/useInView';
import { fadeUp, scaleIn, stagger, wordReveal } from '@/lib/motion';
import { courses, testimonials, features, buildPublicBatchPills } from '@/lib/mockData';
import { filterPublicBatches, getPublicBatchDisplayName } from '@/lib/publicBatches';
import { useEffect, useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/apiClient';

/** Filenames in `public/hero/`. Spaces/special chars are URL-encoded for the browser. */
const HERO_FILES = [
  'A_3D_medical_202604071049.png',
  'A_highly_detailed_202604071050.png',
  'A_highly_detailed_202604071050 (1).png',
  'A_highly_detailed_202604071050 (2).png',
] as const;

const HERO_IMAGES = HERO_FILES.map((name) => `/hero/${encodeURIComponent(name)}`);
const HERO_ROTATE_MS = 2000;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const iconMap: Record<string, any> = {
  MonitorCheck, Brain, Video, ClipboardCheck, MessageCircle, BarChart3, Users, Shield, Award,
};

function HeroImageCarousel() {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => {
      setIndex((i) => (i + 1) % HERO_FILES.length);
    }, HERO_ROTATE_MS);
    return () => window.clearInterval(id);
  }, []);

  return (
    <>
      <div className="absolute inset-0">
        {HERO_IMAGES.map((src, i) => (
          <img
            key={HERO_FILES[i]}
            src={src}
            alt=""
            aria-hidden
            className={`absolute inset-0 w-full h-full object-contain object-top transition-opacity duration-[700ms] ease-out ${i === index ? 'opacity-100 z-[1]' : 'opacity-0 z-0 pointer-events-none'
              }`}
            loading={i === 0 ? 'eager' : 'lazy'}
            decoding="async"
          />
        ))}
      </div>
      <div
        className="absolute bottom-3 left-0 right-0 flex justify-center gap-2 z-[5]"
        aria-hidden
      >
        {HERO_IMAGES.map((_, i) => (
          <span
            key={i}
            className={`h-1.5 rounded-full transition-all duration-300 ${i === index ? 'w-6 bg-mint' : 'w-1.5 bg-chalk/35'
              }`}
          />
        ))}
      </div>
    </>
  );
}

function StatNumber({ value, suffix, label }: { value: number; suffix?: string; label: string }) {
  const display = useOdometer(value);
  return (
    <div>
      <div className="font-display font-black text-slate leading-none" style={{ fontSize: 'clamp(40px, 5vw, 64px)' }}>
        {display}{suffix}
      </div>
      <div className="font-mono text-xs text-ink-faint mt-1 tracking-widest">{label}</div>
    </div>
  );
}

function HeroSection({
  heroPills,
  primaryBatch,
}: {
  heroPills: Array<{ label: string; to: string }>;
  primaryBatch: { label: string; to: string };
}) {
  const h1 = useScramble('MASTER CLASSESS IN CRITICAL CARE.', true);
  const words = h1.split(' ');

  const batchBarBg = '#24628d';

  return (
    <section className="min-h-screen flex flex-col relative">
      <div className="flex flex-col lg:flex-row flex-1 min-h-0">
        {/* Left */}
        <div className="lg:w-[52%] bg-chalk-warm flex flex-col justify-start px-8 lg:px-16 pt-16 lg:pt-20 pb-12 lg:pb-16 relative z-10">
          <motion.div variants={stagger(0.1)} initial="hidden" animate="show">
            {/* Status pill */}

            {/* H1 */}
            <h1 className="font-display font-black text-slate leading-[0.88] tracking-[-0.01em] mb-0" style={{ fontSize: 'clamp(56px, 9vw, 70px)' }}>
              <div className="overflow-hidden">
                {words.map((w, i) => (
                  <motion.span key={i} variants={wordReveal} className="inline-block mr-[0.25em]">
                    {w === 'CARE.' ? (
                      <>CARE MEDICINE<span className="text-mint">.</span></>
                    ) : w}
                  </motion.span>
                ))}
              </div>
            </h1>

            <motion.div variants={fadeUp} className="w-6 h-[1.5px] bg-mint my-7" />

            <motion.p variants={fadeUp} className="font-sans text-lg text-ink-secondary max-w-[420px] leading-[1.8]">
              India's most rigorous online ICU masterclass — built for doctors who operate at the edge of human physiology.
            </motion.p>

            {/* Stats */}
            <motion.div variants={fadeUp} className="flex gap-10 mt-8">
              <StatNumber value={6000} suffix="+" label="DOCTORS TRAINED" />
              <StatNumber value={90} suffix="%" label="EDIC PASS" />
            </motion.div>

            {/* Buttons */}
            <motion.div variants={fadeUp} className="flex flex-wrap gap-4 mt-12">
              <Link to="/courses" className="magnetic border border-border-strong text-ink-secondary rounded-sm px-9 py-4 font-sans text-[15px] hover:border-slate-400 hover:text-ink transition-all duration-300">
                Explore Courses
              </Link>
            </motion.div>
          </motion.div>
        </div>

        {/* Right */}
        <div className="lg:w-[48%] lg:flex-1 bg-chalk-warm flex flex-col items-end relative overflow-hidden min-h-[60vh] lg:min-h-0">
          <div className="relative w-full mt-16 lg:mt-20 h-[280px] sm:h-[340px] lg:h-[430px]">
            <HeroImageCarousel />

            {/* ECG on animated image */}
            <div className="absolute bottom-0 left-0 right-0 h-20 z-[6] pointer-events-none">
              <ECGWaveform className="w-full h-full" />
            </div>

            {/* Pass-rate card on animated image */}
          </div>
        </div>
      </div>

      {/* Batch pills — full-width bar under hero (reference styling) */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        className="w-full shrink-0 py-3.5 px-4 lg:px-8 z-20"
        style={{ backgroundColor: batchBarBg }}
      >
        <div className="max-w-[1400px] mx-auto flex flex-wrap justify-center gap-2.5 sm:gap-3">
          {heroPills.map((pill) => (
            <Link
              key={pill.label}
              to={pill.to}
              className="inline-flex items-center rounded-full bg-white px-4 py-2 sm:px-5 sm:py-2.5 font-sans text-[13px] sm:text-sm font-medium shadow-sm hover:bg-white/95 transition-colors"
              style={{ color: batchBarBg }}
            >
              {pill.label}
            </Link>
          ))}
        </div>
      </motion.div>
    </section>
  );
}

function TickerSection() {
  const items = ['6000+Registration', '40+ PUBLICATIONS', '16+ YEAR OF EXPERIENCE', '15+ BATCHES', '90% EDIC PASS', 'MORE THAN 600 HOURS OF RECORDINGS'];
  return (
    <section className="relative z-30 w-full min-h-[72px] py-3 border-y border-border-soft bg-chalk-stone flex items-center overflow-hidden">
      <div className="font-mono text-xs text-mint tracking-[0.14em] uppercase ml-8 shrink-0 mr-8"></div>
      <div className="flex-1 overflow-hidden relative">
        <div className="animate-marquee flex whitespace-nowrap">
          {[...items, ...items].map((item, i) => (
            <span key={i} className="flex items-center">
              <span className="font-display font-bold text-base text-ink mx-4">{item}</span>
              <span className="text-mint text-xl mx-4">·</span>
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

function MonitorGridSection() {
  const { ref, inView } = useInView();
  const curriculum = [
    'All recorded classes are available from day one of registration and can be watched anytime during the full course tenure on mobile, laptop, or desktop using individual login details.',
    'Covers theory, practical points, and MCQs across the entire critical care medicine syllabus.',
    '10 mock tests with explanation of answers are included.',
    'Case-based approach to support CTCCM/IDCCM/IFCCM, EDIC/EDIAC II, and DM/DrNB exit exam preparation.',
    'MCQs are discussed according to the new pattern of NEET-SS and INI-CET critical care super speciality entrance exams.',
    'Round-the-clock one-to-one doubt clarification for practicing intensivists, anaesthetists, physicians, pulmonologists, and emergency physicians.',
    'Continued academic support to registered delegates through "VOICE OF CRITICAL CARE MEDICINE" even after the batch is over.',
    'Includes many more newer topics and MCQs.',
  ];

  return (
    <section ref={ref} className="bg-monitor-bg scanline py-24 lg:py-36 px-6 lg:px-12 relative">
      <div className="max-w-[1400px] mx-auto">
        <div className="font-mono text-[11px] text-mint tracking-[0.16em] uppercase mb-12">01 / PROGRAMME OVERVIEW</div>

        <motion.div
          variants={stagger(0.1)}
          initial="hidden"
          animate={inView ? 'show' : 'hidden'}
          className="grid grid-cols-1 lg:grid-cols-12 gap-3"
        >
          {/* Cell A */}
          <motion.div variants={scaleIn} className="lg:col-span-7 bg-monitor-card border border-monitor-line rounded-sm p-8 lg:p-10 scanline hover:border-mint/20 transition-all duration-300">
            <div className="font-mono text-[11px] text-mint-dark uppercase tracking-widest mb-6">CURRICULUM</div>
            <div className="font-display font-bold text-4xl text-chalk leading-[1.0] mb-8">Built for Beside Practice<br />and Exam Preparation</div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {curriculum.map((item) => (
                <div key={item} className="flex items-center gap-3">
                  <span className="font-mono text-[13px] text-mint-dark">→</span>
                  <span className="font-sans text-sm text-chalk/70">{item}</span>
                </div>
              ))}
            </div>
          </motion.div>

          {/* Cell B */}
          <motion.div variants={scaleIn} className="lg:col-span-5 lg:row-span-2 relative rounded-sm overflow-hidden min-h-[300px] flex items-center justify-center">
            <img src="https://images.unsplash.com/photo-1631815589968-fdb09a223b1e?w=900&q=85" alt="ICU equipment" className="img-doc w-1/2 h-1/2 object-cover opacity-70" style={{ mixBlendMode: 'luminosity' }} />
            <div className="absolute bottom-0 left-0 right-0 p-6 bg-gradient-to-t from-monitor-bg/90 to-transparent">
              <div className="font-mono text-[10px] text-mint-dark uppercase mb-1">ICU ENVIRONMENT</div>
              <div className="font-display font-bold text-xl text-chalk">Learn in context.</div>
            </div>
          </motion.div>

          {/* Cell D */}

          {/* Cell E - full bottom */}
          <motion.div variants={scaleIn} className="lg:col-span-12 bg-monitor-card border border-monitor-line rounded-sm p-8 hover:border-mint/20 transition-all duration-300">
            <div className="flex flex-wrap justify-around items-center gap-6">
              {[{ num: '3000+', label: 'MCQs' }, { num: '50+', label: 'Case Based Teaching' }, { num: '1000+', label: 'Computer/Table Viva Based Questions' }].map((s, i) => (
                <div key={i} className="flex items-center gap-6">
                  {i > 0 && <div className="w-px h-10 bg-monitor-line hidden sm:block" />}
                  <div className="text-center">
                    <div className="font-display font-extrabold text-4xl text-chalk">{s.num}</div>
                    <div className="font-mono text-[10px] text-chalk/40 mt-1">{s.label}</div>
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
}

function WhoSection() {
  const { ref, inView } = useInView();
  const attendees = [
    {
      icon: Activity,
      title: 'Practicing Doctors',
      desc: 'Those practicing Critical Care Medicine, Anaesthesia, Pulmonology, General Medicine, and Emergency Medicine who want to learn and upgrade their knowledge in critical care medicine.',
    },
    {
      icon: GraduationCap,
      title: 'Postgraduate Trainees',
      desc: 'Those doing postgraduation in Anaesthesia, Pulmonology, General Medicine, and Emergency Medicine and interested in choosing Critical Care as a career option.',
    },
    {
      icon: Award,
      title: 'Critical Care Programs',
      desc: 'Those currently pursuing CTCCM, IDCCM, IFCCM, PDCC, DrNB, or DM in Critical Care.',
    },
    {
      icon: BookOpen,
      title: 'EDIC/EDIAC Preparation',
      desc: 'Those preparing for EDIC/EDIAC Part I and Part II.',
    },
    {
      icon: Stethoscope,
      title: 'Entrance Exam Preparation',
      desc: 'Those preparing for NEET Super Speciality and INISS-CET entrance.',
    },
  ];

  return (
    <section ref={ref} className="bg-chalk-warm py-24 lg:py-36 px-6 lg:px-12 clip-top">
      <div className="max-w-[1400px] mx-auto">
        <div className="flex flex-col lg:flex-row justify-between lg:items-end mb-16 gap-8">
          <h2 className="font-display font-extrabold text-slate leading-[0.92]" style={{ fontSize: 'clamp(48px, 7vw, 88px)' }}>
            WHO<br />SHOULD<br />ATTEND?
          </h2>
          <p className="font-sans text-base text-ink-secondary max-w-[300px] leading-[1.8]">
            Designed for doctors who operate at the margins of human physiology and want mastery over it.
          </p>
        </div>

        <motion.div
          variants={stagger(0.08)}
          initial="hidden"
          animate={inView ? 'show' : 'hidden'}
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3"
        >
          {attendees.map((item, i) => {
            const Icon = item.icon;
            return (
              <motion.div
                key={i}
                variants={scaleIn}
                className="bg-chalk border border-border-soft rounded-sm p-8 relative overflow-hidden hover:border-mint/30 hover:shadow-mint transition-all duration-400 group cursor-pointer"
              >
                <span className="font-mono text-[11px] text-ink-faint absolute top-5 right-5" style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}>
                  {String(i + 1).padStart(2, '0')}
                </span>
                <Icon size={22} className="text-ink-faint group-hover:text-mint transition-colors mt-2" />
                <div className="font-display font-bold text-xl text-slate mt-5 mb-2">{item.title}</div>
                <div className="font-sans text-sm text-ink-muted leading-[1.7]">{item.desc}</div>
                <div className="w-0 group-hover:w-8 h-[2px] bg-mint transition-all duration-500 mt-6" />
              </motion.div>
            );
          })}
        </motion.div>
      </div>
    </section>
  );
}

function FeaturesSection() {
  const { ref, inView } = useInView();
  return (
    <section ref={ref} className="bg-chalk py-24 lg:py-36 px-6 lg:px-12">
      <div className="max-w-[1400px] mx-auto">
        <div className="font-mono text-[11px] text-mint uppercase tracking-[0.16em] mb-5">02 / WHY THIS WORKS</div>
        <div className="flex flex-col lg:flex-row justify-between lg:items-end mb-16 gap-8">
          <h2 className="font-display font-extrabold text-slate leading-[0.95]" style={{ fontSize: 'clamp(44px, 6vw, 76px)' }}>
            BUILT FROM<br />16 YEARS AT<br />THE BEDSIDE.
          </h2>
          <p className="font-sans text-base text-ink-secondary max-w-[340px] leading-[1.8]">
            Every lecture, every MCQ, every protocol is drawn from real-world ICU evidence — not textbook theory.
          </p>
        </div>
        <div className="w-full h-px bg-border-soft mb-16" />

        <motion.div
          variants={stagger(0.06)}
          initial="hidden"
          animate={inView ? 'show' : 'hidden'}
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3"
        >
          {features.map((f, i) => {
            const Icon = iconMap[f.icon] || MonitorCheck;
            return (
              <motion.div
                key={i}
                variants={scaleIn}
                className="bg-chalk-warm border border-border-soft rounded-sm p-8 hover:bg-chalk hover:border-border-strong hover:shadow-sm transition-all duration-300 group"
              >
                <Icon size={20} className="text-mint-dark group-hover:text-mint transition-colors" />
                <div className="font-display font-bold text-xl text-slate mt-5 mb-2">{f.title}</div>
                <div className="font-sans text-sm text-ink-muted leading-[1.7]">{f.desc}</div>
              </motion.div>
            );
          })}
        </motion.div>

        {/* Stats bar */}
        <div className="bg-slate py-10 px-8 lg:px-12 rounded-sm mt-16 flex flex-col lg:flex-row justify-between items-center gap-6">
          <div className="font-display font-bold italic text-2xl lg:text-[28px] text-chalk">
            "6000+ doctors. 15 batches. 90% pass rate."
          </div>
        </div>
      </div>
    </section>
  );
}



function TestimonialCard({ t }: { t: any }) {
  return (
    <div className="w-[350px] sm:w-[550px] shrink-0 bg-chalk border border-border-soft rounded-sm p-8 sm:p-10 hover:shadow-lg hover:border-mint/20 transition-all duration-300 mx-3 group flex flex-col">
      <div className="flex items-center gap-1 mb-6 text-mint">
        {[...Array(5)].map((_, i) => (
          <svg key={i} className="w-4 h-4 fill-current" viewBox="0 0 20 20">
            <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
          </svg>
        ))}
      </div>
      <div className="flex-1 overflow-visible">
        <p className="font-display font-medium italic text-base sm:text-lg text-ink-secondary leading-[1.7] whitespace-pre-wrap group-hover:text-slate transition-colors">
          "{t.quote}"
        </p>
      </div>
    </div>
  );
}

function TestimonialsSection({ data }: { data?: any[] }) {
  // Use DB data if available, otherwise fallback to mock
  const list = data && data.length > 0 ? data : testimonials;

  const items = list.map(t => ({
    quote: (t.text || t.quote || "").trim(),
    name: t.name || 'Verified Student',
    role: t.role || 'Critical Care Professional',
    institution: t.institution || ''
  })).filter(t => t.quote.length > 0);

  // Triple the items for a seamless loop if the list is short
  const displayItems = [...items, ...items, ...items];
  const marqueeDurationSeconds = Math.max(180, items.length * 35); // slower: ~35s per card, with a longer minimum

  return (
    <section className="bg-chalk-warm py-24 lg:py-36 overflow-hidden relative">
      {/* Background decoration */}
      <div className="absolute top-0 left-0 w-full h-full opacity-[0.03] pointer-events-none overflow-hidden">
        <div className="absolute top-[-10%] left-[-5%] w-[40%] h-[40%] bg-mint rounded-full blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[-5%] w-[40%] h-[40%] bg-slate rounded-full blur-[120px]" />
      </div>

      <div className="max-w-[1400px] mx-auto px-6 lg:px-12 mb-16">
        <div className="font-mono text-[11px] text-mint mb-5 tracking-[0.16em] uppercase">03 / VOICES FROM THE BEDSIDE</div>
        <h2 className="font-display font-extrabold text-slate leading-[0.92]" style={{ fontSize: 'clamp(44px, 6vw, 76px)' }}>
          WHAT<br />DOCTORS SAY.
        </h2>
      </div>

      {/* Marquee Row */}
      <div className="relative flex overflow-hidden group py-4">
        <motion.div
          animate={{
            x: ["0%", "-50%"]
          }}
          transition={{
            x: {
              repeat: Infinity,
              repeatType: "loop",
              duration: marqueeDurationSeconds,
              ease: "linear",
            },
          }}
          className="flex whitespace-nowrap"
        >
          {/* Double items for seamless loop */}
          {[...items, ...items].map((t, i) => (
            <TestimonialCard key={i} t={t} />
          ))}
        </motion.div>
      </div>

      {/* Stats bar */}
      <div className="max-w-[1400px] mx-auto px-6 lg:px-12 mt-20">
        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="bg-slate rounded-sm p-8 lg:p-12 relative overflow-hidden scanline">
          <div className="flex flex-wrap justify-between gap-10 relative z-10">
            {[{ n: 6000, s: "+", l: 'Doctors Trained' }, { n: 15, s: "", l: 'Batches Completed' }, { n: 90, s: "%", l: 'EDIC Pass Rate' }].map((s) => (
              <StatBarItem key={s.l} num={s.n} suffix={s.s} label={s.l} />
            ))}
          </div>
          <div className="absolute top-0 right-0 p-8 opacity-10">
            <Quote size={80} className="text-mint" />
          </div>
        </motion.div>
      </div>
    </section>
  );
}

function StatBarItem({ num, suffix, label }: { num: number; suffix: string; label: string }) {
  const display = useOdometer(num);
  return (
    <div className="flex items-center gap-3">
      <span className="font-display font-black text-5xl lg:text-6xl text-chalk">{display}{suffix}</span>
      <span className="font-sans text-[13px] text-chalk/50 uppercase tracking-wider">{label}</span>
    </div>
  );
}

function CoursesSection({ batches }: { batches?: any[] }) {
  return (
    <section className="bg-chalk py-24 lg:py-36 px-6 lg:px-12">
      <div className="max-w-[1400px] mx-auto">
        <div className="font-mono text-[11px] text-mint mb-5 tracking-[0.16em] uppercase">04 / PROGRAMMES</div>
        <h2 className="font-display font-extrabold text-slate leading-[0.92] mb-16" style={{ fontSize: 'clamp(44px, 6vw, 76px)' }}>
          CHOOSE<br />YOUR PATH.
        </h2>

        <div className="divide-y divide-border-soft">
          {batches?.map((c, i) => (
            <Link
              key={c.batch_slug}
              to={`/register/${encodeURIComponent(c.batch_slug)}`}
              className="flex flex-col lg:flex-row lg:items-center justify-between py-9 group cursor-pointer hover:bg-ink-ghost hover:px-6 hover:-mx-6 rounded-sm transition-all duration-300"
            >
              <div className="flex items-center gap-6 mb-3 lg:mb-0">
                <span className="font-mono text-xs text-ink-faint group-hover:text-mint w-8 shrink-0 transition-colors">
                  {String(i + 1).padStart(2, '0')}
                </span>
                <div>
                  <div className="font-display font-bold text-xl text-slate group-hover:text-slate-light transition-colors">{getPublicBatchDisplayName(c as any)}</div>
                  <div className="font-mono text-[11px] text-ink-faint mt-1">
                    {c.launch_ready ? 'Registration Open' : 'Coming Soon'} · {c.status === '1' ? 'Active' : 'Inactive'}
                  </div>
                  {c.description && (
                    <p className="font-sans text-[13px] text-ink-muted mt-2 max-w-xl line-clamp-2">
                      {c.description}
                    </p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-4 lg:gap-6 ml-14 lg:ml-0">
                <span className="font-mono text-[10px] border border-border-soft rounded-sm px-3 py-1 text-ink-faint">
                  {c.launch_ready ? 'Enrolling now' : 'Waitlist'}
                </span>
                <ArrowUpRight size={15} className="text-ink-faint group-hover:text-mint transition-all" />
              </div>
            </Link>
          ))}
          {(!batches || batches.length === 0) && (
            <div className="py-12 text-center font-mono text-xs text-ink-faint italic">No active batches found in the catalogue.</div>
          )}
        </div>
      </div>
    </section>
  );
}

export default function Home() {
  const { data: regBatches } = useQuery<Array<{ slug: string; title: string }>>({
    queryKey: ['regBatches'],
    queryFn: () => apiClient('/registration/batches'),
  });
  const { data: catalogRaw } = useQuery<any[]>({
    queryKey: ['registrationCatalogHome'],
    queryFn: () => apiClient('/registration/catalog?include_inactive=true'),
  });

  const { data: dbTestimonials } = useQuery<any[]>({
    queryKey: ['publicTestimonials'],
    queryFn: () => apiClient('/registration/testimonials'),
  });

  const catalog = useMemo(() => {
    if (!catalogRaw) return [];
    return filterPublicBatches(catalogRaw as any[]);
  }, [catalogRaw]);

  const heroPills = buildPublicBatchPills(regBatches);
  const primaryBatch = heroPills[0] || { label: 'Batch', to: '/register' };

  return (
    <div className="min-h-screen">
      <Navbar />
      <HeroSection heroPills={heroPills} primaryBatch={primaryBatch} />
      <TickerSection />
      <MonitorGridSection />
      <WhoSection />
      <FeaturesSection />
      <TestimonialsSection data={dbTestimonials} />
      <CoursesSection batches={catalog} />
      <Footer />
    </div>
  );
}
