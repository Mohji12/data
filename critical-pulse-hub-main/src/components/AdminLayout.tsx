import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { Menu } from 'lucide-react';
import {
  LayoutDashboard,
  Users,
  Video,
  FolderOpen,
  Layers,
  ClipboardCheck,
  MessageSquare,
  MessageCircle,
  BarChart3,
  Ticket,
  CalendarDays,
  Settings,
  Activity,
  LogOut,
  CreditCard,
  Package,
  ListTree,
  Percent,
  Quote,
  Building2,
  CircleHelp,
  Send,
  Mail,
} from 'lucide-react';
import { useAuthStore } from '@/store/authStore';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet';

const navItems = [
  {
    label: 'OVERVIEW',
    items: [{ label: 'Dashboard', to: '/admin', icon: LayoutDashboard, match: 'exact' as const }],
  },
  {
    label: 'COMMUNICATION',
    items: [
      { label: 'WhatsApp', to: '/admin/communication/whatsapp', icon: Send },
      { label: 'Bulk Mail', to: 'https://staging.d5w312h4wy6nw.amplifyapp.com/', icon: Mail },
    ],
  },
  {
    label: 'USERS',
    items: [
      { label: 'All Users', to: '/admin/users', icon: Users },
      { label: 'Login Activity', to: '/admin/login-activity', icon: Activity },
    ],
  },
  {
    label: 'COMMERCE',
    items: [
      { label: 'Payments', to: '/admin/payments', icon: CreditCard },
      { label: 'Packages', to: '/admin/packages', icon: Package },
      { label: 'Extensions', to: '/admin/extensions', icon: Layers },
      { label: 'Coupons', to: '/admin/coupons', icon: Ticket },
      { label: 'Event registrations', to: '/admin/events', icon: CalendarDays },
    ],
  },
  {
    label: 'CONTENT',
    items: [
      { label: 'Videos', to: '/admin/content/videos', icon: Video },
      { label: 'Folders', to: '/admin/content/folders', icon: FolderOpen },
      { label: 'Batches', to: '/admin/content/batches', icon: Layers },
      { label: 'Video questions', to: '/admin/content/video-questions', icon: CircleHelp },
    ],
  },
  {
    label: 'ASSESSMENT',
    items: [
      { label: 'Exams', to: '/admin/quiz/exams', icon: ClipboardCheck },
      { label: 'Questions', to: '/admin/quiz/questions', icon: MessageSquare },
      { label: 'Quiz sections', to: '/admin/quiz/sections', icon: ListTree },
      { label: 'Marking types', to: '/admin/quiz/marking-types', icon: Percent },
      { label: 'Results', to: '/admin/quiz/results', icon: BarChart3 },
    ],
  },
  {
    label: 'MISC',
    items: [
      { label: 'Testimonials', to: '/admin/testimonials', icon: Quote },
      { label: 'Auditorium', to: '/admin/auditorium', icon: Building2 },
    ],
  },
  {
    label: 'SETTINGS',
    items: [{ label: 'Site options', to: '/admin/settings', icon: Settings }],
  },
];

export default function AdminLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { logout, user } = useAuthStore();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const isActive = (to: string, match?: 'exact') => {
    if (match === 'exact') return location.pathname === to;
    if (location.pathname === to) return true;
    return location.pathname.startsWith(`${to}/`);
  };

  const roleLabel =
    user?.role === 'admin'
      ? (user.userType || '').toLowerCase() === 'techadmin'
        ? 'TECH ADMIN'
        : 'ADMIN'
      : '';

  const renderNav = (onNavigate?: () => void) =>
    navItems.map((section) => (
      <div key={section.label}>
        <div className="font-mono text-[10px] text-chalk/30 tracking-[0.14em] uppercase px-5 mb-2 mt-6">{section.label}</div>
        {section.items.map((item) => {
          const Icon = item.icon;
          const isExternal = /^https?:\/\//i.test(item.to);
          const active = isActive(item.to, 'match' in item ? item.match : undefined);
          return isExternal ? (
            <a
              key={item.to}
              href={item.to}
              target="_blank"
              rel="noopener noreferrer"
              onClick={onNavigate}
              className="flex items-center gap-3 py-2.5 px-4 mx-3 rounded transition-all duration-200 text-sm font-sans text-chalk/50 hover:text-chalk hover:bg-white/[0.05]"
            >
              <Icon size={16} />
              <span>{item.label}</span>
            </a>
          ) : (
            <Link
              key={item.to}
              to={item.to}
              onClick={onNavigate}
              className={`flex items-center gap-3 py-2.5 px-4 mx-3 rounded transition-all duration-200 text-sm font-sans ${
                active
                  ? 'bg-white/[0.08] text-chalk border-l-2 border-mint'
                  : 'text-chalk/50 hover:text-chalk hover:bg-white/[0.05]'
              }`}
            >
              <Icon size={16} />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </div>
    ));

  return (
    <div className="flex min-h-screen">
      <aside className="hidden lg:flex flex-col w-60 bg-monitor-card fixed top-0 bottom-0 z-30 overflow-y-auto">
        <div className="px-5 pt-6 pb-2 flex items-center gap-3">
          <Link to="/" className="flex items-center gap-2">
            <img
              src="/hero/logo.png"
              alt="Critical Care Medicine Logo"
              className="h-8 w-auto object-contain"
            />
          </Link>
          <span className="font-mono text-[10px] bg-amber-glow text-amber border border-amber/30 rounded-sm px-2.5 py-1">
            {roleLabel || 'ADMIN'}
          </span>
        </div>

        <nav className="flex-1 mt-4">{renderNav()}</nav>

        <div className="border-t border-white/10 pt-5 px-5 pb-5 mt-auto">
          {user?.role === 'admin' && user.email && (
            <div className="font-mono text-[10px] text-chalk/40 mb-3 truncate" title={user.email}>
              {user.email}
            </div>
          )}
          <button
            type="button"
            onClick={() => {
              void logout();
              navigate('/admin/login');
            }}
            className="flex items-center gap-2 text-chalk/40 hover:text-blush transition-colors font-mono text-xs"
          >
            <LogOut size={14} />
            Sign Out
          </button>
        </div>
      </aside>

      <div className="flex-1 min-w-0 lg:ml-60 bg-chalk-warm min-h-screen">
        <header className="lg:hidden sticky top-0 z-40 flex items-center justify-between gap-3 border-b border-border-soft bg-monitor-card px-4 py-3">
          <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
            <SheetTrigger asChild>
              <button
                type="button"
                className="inline-flex items-center gap-2 rounded-sm border border-white/10 px-3 py-2 text-chalk font-sans text-sm"
                aria-label="Open admin menu"
              >
                <Menu size={18} />
                Menu
              </button>
            </SheetTrigger>
            <SheetContent side="left" className="w-[min(100vw,18rem)] bg-monitor-card border-white/10 p-0 overflow-y-auto">
              <SheetHeader className="px-5 pt-6 pb-2 text-left">
                <SheetTitle className="text-chalk font-display">Admin</SheetTitle>
              </SheetHeader>
              <nav className="pb-8">{renderNav(() => setMobileNavOpen(false))}</nav>
            </SheetContent>
          </Sheet>
          <span className="font-mono text-[10px] bg-amber-glow text-amber border border-amber/30 rounded-sm px-2 py-0.5">
            {roleLabel || 'ADMIN'}
          </span>
        </header>
        <Outlet />
      </div>
    </div>
  );
}
