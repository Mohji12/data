import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AlignJustify, X, ChevronDown, Facebook, Instagram, Linkedin } from 'lucide-react';
import { useAuthStore } from '@/store/authStore';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/apiClient';
import { resolvePublicUploadUrl } from '@/lib/apiBase';
import { filterPublicBatches, getPublicBatchDisplayName, type RegistrationCatalogRow } from '@/lib/publicBatches';
import { EVENT_DISPLAY_NAME, EVENT_REGISTER_PATH } from '@/lib/eventConclave';

const navLinks = [
  { label: 'Home', to: '/' },
  { label: 'Faculty', to: '/faculty' },
  { label: 'Courses', to: '/courses', hasDropdown: true },
  { label: 'Membership', to: '/membership' },
  { label: 'Awards', to: '/awards' },
  { label: 'Publications', to: '/publications' },
  { label: 'Gallery', to: '/gallery' },
  { label: 'FAQ', to: '/faq' },
  { label: 'Contact', to: '/contact' },
];

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [coursesOpen, setCoursesOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated, user } = useAuthStore();
  const dropdownRef = useRef<HTMLDivElement>(null);
  const { data: catalog } = useQuery<RegistrationCatalogRow[]>({
    // Keep this identical to Home ("Choose your path") source to avoid divergence.
    queryKey: ['registrationCatalogHome'],
    queryFn: () => apiClient('/registration/catalog?include_inactive=true'),
  });
  const publicCatalog = filterPublicBatches(catalog || []);
  const batchOptions = publicCatalog.map((b) => ({
    label: getPublicBatchDisplayName(b),
    to: `/register/${encodeURIComponent(b.batch_slug)}`,
    launch_ready: Boolean(b.launch_ready),
  }));
  const brochureCourses = publicCatalog;

  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 60);
    window.addEventListener('scroll', handler, { passive: true });
    return () => window.removeEventListener('scroll', handler);
  }, []);

  useEffect(() => {
    setMobileOpen(false);
    setCoursesOpen(false);
  }, [location]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setCoursesOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <>
      {/* Top utility bar */}
      <div className="fixed top-0 left-0 right-0 z-[51] h-10 bg-slate flex items-center">
        <div className="w-full max-w-[1400px] mx-auto px-6 flex items-center justify-between">
          {/* Social icons */}
          <div className="flex items-center gap-3">
            <a href="https://www.facebook.com/dr.harish.mm" target="_blank" rel="noopener noreferrer" className="w-7 h-7 rounded-full border border-white/20 flex items-center justify-center hover:border-mint hover:text-mint transition-colors text-white/60">
              <Facebook size={13} />
            </a>
            <a href="https://www.instagram.com/dr.harish.mallapura?r=nametag" target="_blank" rel="noopener noreferrer" className="w-7 h-7 rounded-full border border-white/20 flex items-center justify-center hover:border-mint hover:text-mint transition-colors text-white/60">
              <Instagram size={13} />
            </a>
            <a href="https://www.linkedin.com/in/harish-d-b5a74243" target="_blank" rel="noopener noreferrer" className="w-7 h-7 rounded-full border border-white/20 flex items-center justify-center hover:border-mint hover:text-mint transition-colors text-white/60">
              <Linkedin size={13} />
            </a>
          </div>

          {/* Batch selector + quick login */}
          <div className="hidden md:flex items-center gap-2">
            <select
              defaultValue=""
              onChange={(e) => {
                const to = e.target.value;
                if (to) navigate(to);
              }}
              className="h-8 min-w-[250px] bg-white/95 text-slate border border-white/30 rounded-md px-2 font-sans text-xs"
            >
              <option value="">Select Batch</option>
              {batchOptions.map((opt) => (
                <option key={opt.label} value={opt.to}>
                  {opt.label}
                </option>
              ))}
            </select>
            <Link
              to={EVENT_REGISTER_PATH}
              className="h-8 inline-flex items-center rounded-md border border-mint/35 px-3 font-sans text-xs font-semibold text-mint hover:border-mint hover:bg-mint/10 transition-colors whitespace-nowrap"
            >
              {EVENT_DISPLAY_NAME}
            </Link>
            <Link
              to="/login"
              className="h-8 inline-flex items-center rounded-md border border-white/25 px-3 font-sans text-xs font-semibold text-white/85 hover:border-mint hover:text-mint transition-colors"
            >
              Login
            </Link>
          </div>
        </div>
      </div>

      {/* Main navbar */}
      <header
        className={`fixed top-10 left-0 right-0 z-50 h-16 flex items-center transition-all duration-300 ${
          scrolled
            ? 'bg-chalk-warm/95 backdrop-blur-xl border-b border-border-soft shadow-xs'
            : 'bg-chalk-warm/95 backdrop-blur-xl border-b border-border-soft'
        }`}
      >
        <div className="w-full max-w-[1400px] mx-auto px-6 flex items-center justify-between">
          {/* Logo */}
          <Link to="/" className="flex items-center">
            <img 
              src="/hero/logo.png" 
              alt="Critical Care Medicine Logo" 
              className="h-14 w-auto object-contain"
            />
          </Link>

          {/* Center nav */}
          <nav className="hidden lg:flex items-center gap-7">
            {navLinks.map((link) => (
              <div key={link.to} className="relative" ref={link.hasDropdown ? dropdownRef : undefined}>
                {link.hasDropdown ? (
                  <button
                    onClick={() => setCoursesOpen(!coursesOpen)}
                    className={`nav-strike font-sans text-[14px] font-medium flex items-center gap-1 transition-colors ${
                      link.hasDropdown
                        ? location.pathname === '/courses'
                          ? 'text-mint'
                          : 'text-ink-secondary hover:text-mint'
                        : location.pathname === link.to
                          ? 'text-mint'
                          : 'text-ink-secondary hover:text-mint'
                    }`}
                  >
                    {link.label}
                    <ChevronDown size={14} className={`transition-transform duration-200 ${coursesOpen ? 'rotate-180' : ''}`} />
                  </button>
                ) : (
                  <Link
                    to={link.to}
                    className={`nav-strike font-sans text-[14px] font-medium transition-colors ${
                      location.pathname === link.to ? 'text-mint' : 'text-ink-secondary hover:text-mint'
                    }`}
                  >
                    {link.label}
                  </Link>
                )}

                {/* Courses dropdown */}
                {link.hasDropdown && (
                  <AnimatePresence>
                    {coursesOpen && (
                      <motion.div
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: 8 }}
                        transition={{ duration: 0.2 }}
                        className="absolute top-full left-1/2 -translate-x-1/2 mt-3 w-[260px] bg-chalk-paper border border-border-soft rounded-md shadow-lg p-2 z-50"
                      >
                        {brochureCourses.map((course) => {
                          const href = resolvePublicUploadUrl(course.brochure_url);
                          return (
                            <a
                              key={course.batch_slug}
                              href={href || '#'}
                              target={href ? '_blank' : undefined}
                              rel={href ? 'noreferrer' : undefined}
                              onClick={(e) => {
                                if (!href) e.preventDefault();
                              }}
                              className="flex items-center gap-3 px-3 py-2.5 rounded hover:bg-ink-ghost transition-colors group"
                            >
                              <div className="w-1.5 h-1.5 rounded-full bg-mint shrink-0" />
                              <div>
                                <div className="font-sans text-[13px] font-medium text-ink group-hover:text-mint transition-colors">{getPublicBatchDisplayName(course)}</div>
                                <div className="font-mono text-[10px] text-ink-faint mt-0.5">
                                  {href ? 'Open brochure PDF' : (course.launch_ready ? 'Brochure not uploaded' : 'Coming soon')}
                                </div>
                              </div>
                            </a>
                          );
                        })}
                        {brochureCourses.length === 0 && (
                          <div className="px-3 py-2.5 font-mono text-[11px] text-ink-faint">No course brochures available</div>
                        )}
                      </motion.div>
                    )}
                  </AnimatePresence>
                )}
              </div>
            ))}
          </nav>

          {/* Right */}
          <div className="hidden lg:flex items-center gap-3">
            {isAuthenticated ? (
              null
            ) : (
              <>
                <Link
                  to="/login"
                  className="font-sans text-[13px] font-semibold text-ink border border-border-strong rounded-full px-6 py-2 hover:border-ink hover:text-ink transition-all"
                >
                  Login
                </Link>
                <Link
                  to="/register"
                  className="magnetic bg-mint text-slate rounded-full px-6 py-2 font-sans font-semibold text-[13px] hover:bg-mint-light shadow-xs transition-all duration-300"
                >
                  Register Now
                </Link>
              </>
            )}
          </div>

          {/* Mobile toggle */}
          <button className="lg:hidden text-ink" onClick={() => setMobileOpen(true)}>
            <AlignJustify size={22} />
          </button>
        </div>
      </header>

      {/* Spacer for fixed navbar */}
      <div className="h-[104px]" />

      {/* Mobile menu */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ clipPath: 'inset(0 0 100% 0)' }}
            animate={{ clipPath: 'inset(0 0 0% 0)' }}
            exit={{ clipPath: 'inset(0 0 100% 0)' }}
            transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
            className="fixed inset-0 z-[60] bg-slate flex flex-col items-center justify-center gap-6"
          >
            <button className="absolute top-5 right-6 text-white" onClick={() => setMobileOpen(false)}>
              <X size={24} />
            </button>
            {navLinks.map((link) =>
              link.hasDropdown ? (
                <div key={link.to} className="flex flex-col items-center gap-3 w-full max-w-md px-4">
                  <Link to={link.to} className="nav-strike font-display text-5xl font-bold text-white">
                    {link.label}
                  </Link>
                  <div className="w-full rounded-sm border border-white/15 bg-white/5 px-4 py-3 max-h-[38vh] overflow-y-auto">
                    <div className="font-mono text-[10px] text-white/50 uppercase tracking-wider mb-2">Brochures (PDF)</div>
                    {brochureCourses.length === 0 ? (
                      <p className="font-mono text-xs text-white/40 text-center py-2">No brochures available</p>
                    ) : (
                      <ul className="space-y-2">
                        {brochureCourses.map((course) => {
                          const href = resolvePublicUploadUrl(course.brochure_url);
                          return (
                            <li key={course.batch_slug}>
                              <a
                                href={href || '#'}
                                target={href ? '_blank' : undefined}
                                rel={href ? 'noreferrer' : undefined}
                                onClick={(e) => {
                                  if (!href) e.preventDefault();
                                  setMobileOpen(false);
                                }}
                                className="font-sans text-sm text-mint hover:underline block"
                              >
                                {getPublicBatchDisplayName(course)}
                                <span className="font-mono text-[10px] text-white/40 block">
                                  {href ? 'Open PDF →' : 'Brochure not uploaded'}
                                </span>
                              </a>
                            </li>
                          );
                        })}
                      </ul>
                    )}
                  </div>
                </div>
              ) : (
                <Link key={link.to} to={link.to} className="nav-strike font-display text-5xl font-bold text-white">
                  {link.label}
                </Link>
              )
            )}
            <div className="mt-8 flex gap-4">
              <Link to="/login" className="font-sans text-sm text-white/60 border border-white/20 rounded-full px-6 py-2 hover:text-white hover:border-white/40 transition-colors">
                Login
              </Link>
              <Link to="/register" className="bg-mint text-slate rounded-full px-6 py-2 font-sans font-semibold text-sm">
                Register Now
              </Link>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
