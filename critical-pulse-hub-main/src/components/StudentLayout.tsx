import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import { LayoutDashboard, PlayCircle, ClipboardCheck, User, CreditCard, LogOut, Home, BookOpen, FileQuestion } from 'lucide-react';
import { useAuthStore } from '@/store/authStore';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/apiClient';

const navItems = [
  { label: 'LEARN', items: [
    { label: 'Dashboard', to: '/dashboard', icon: LayoutDashboard },
    { label: 'Video Library', to: '/dashboard/videos', icon: PlayCircle },
    { label: 'Mock Tests', to: '/dashboard/quiz', icon: ClipboardCheck },
  ]},
  { label: 'ACCOUNT', items: [
    { label: 'Profile', to: '/dashboard/profile', icon: User },
    { label: 'Payments', to: '/dashboard/payments', icon: CreditCard },
  ]},
];

export default function StudentLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();
  const { data: summary } = useQuery({
    queryKey: ['dashboardSummaryNav'],
    queryFn: () => apiClient('/dashboard/summary'),
    enabled: !!user?.id,
  });
  const isActive = (to: string) => location.pathname === to || (to !== '/dashboard' && location.pathname.startsWith(to));
  const canExtend = !!summary?.extension?.enabled;
  const learnItems = [
    { label: 'Dashboard', to: '/dashboard', icon: LayoutDashboard },
    { label: 'Video Library', to: '/dashboard/videos', icon: PlayCircle },
    { label: 'Mock Tests', to: '/dashboard/quiz', icon: ClipboardCheck },
    ...(canExtend ? [{ label: 'Extend Subscription', to: '/dashboard/extend-subscription', icon: BookOpen }] : []),
  ];
  const mobileNav = [
    { label: 'Home', to: '/dashboard', icon: Home },
    { label: 'Videos', to: '/dashboard/videos', icon: PlayCircle },
    { label: 'Tests', to: '/dashboard/quiz', icon: FileQuestion },
    ...(canExtend ? [{ label: 'Extend', to: '/dashboard/extend-subscription', icon: BookOpen }] : []),
    { label: 'Profile', to: '/dashboard/profile', icon: User },
  ];

  return (
    <div className="flex min-h-screen bg-chalk-warm">
      {/* Sidebar - desktop */}
      <aside className="hidden lg:flex flex-col w-60 bg-chalk-cool border-r border-border-soft fixed top-0 bottom-0 z-30">
        <div className="px-5 pt-6 pb-2">
          <Link to="/" className="flex items-center gap-2">
            <img
              src="/hero/logo.png"
              alt="Critical Care Medicine Logo"
              className="h-8 w-auto object-contain"
            />
            <span className="font-mono text-[10px] text-mint tracking-[0.2em] uppercase font-medium">STUDENT</span>
          </Link>
        </div>
        <div className="w-full h-px bg-border-soft my-4" />

        <nav className="flex-1 overflow-y-auto">
          {navItems.map((section) => (
            <div key={section.label}>
              <div className="font-mono text-[10px] text-ink-faint tracking-[0.14em] uppercase px-5 mb-2 mt-6">
                {section.label}
              </div>
              {(section.label === 'LEARN' ? learnItems : section.items).map((item) => {
                const Icon = item.icon;
                const active = isActive(item.to);
                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    className={`flex items-center gap-3 py-2.5 px-4 mx-3 rounded transition-all duration-200 ${
                      active
                        ? 'bg-mint-pale text-slate border-l-2 border-mint'
                        : 'text-ink-secondary hover:bg-ink-ghost hover:text-ink'
                    }`}
                  >
                    <Icon size={16} />
                    <span className="font-sans text-sm font-medium">{item.label}</span>
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>

        <div className="border-t border-border-soft pt-5 px-5 pb-5 mt-auto">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-sm bg-mint-pale border border-mint/30 flex items-center justify-center font-mono text-[13px] text-slate font-medium">
              {user?.initials || 'RS'}
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-sans text-[13px] font-medium text-ink truncate">{user?.name || 'Dr. Sharma'}</div>
              <div className="font-mono text-[11px] text-ink-muted truncate">{user?.email || 'rahul@apollo.com'}</div>
            </div>
            <button
              onClick={() => { logout(); navigate('/'); }}
              className="text-ink-faint hover:text-blush transition-colors ml-auto"
            >
              <LogOut size={15} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 lg:ml-60 flex flex-col min-h-screen pb-16 lg:pb-0">
        <Outlet />
      </div>

      {/* Mobile bottom tab */}
      <nav className="lg:hidden fixed bottom-0 left-0 right-0 z-30 bg-chalk-cool border-t border-border flex justify-around py-2">
        {mobileNav.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.to);
          return (
            <Link
              key={item.to}
              to={item.to}
              className={`flex flex-col items-center gap-1 py-1 px-3 ${active ? 'text-mint' : 'text-ink-faint'}`}
            >
              <Icon size={18} />
              <span className="text-[10px] font-mono">{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
