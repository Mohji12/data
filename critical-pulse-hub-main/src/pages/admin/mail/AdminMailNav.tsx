import { Link, useLocation } from 'react-router-dom';

const items = [
  { to: '/admin/mail', label: 'Dashboard', match: 'exact' as const },
  { to: '/admin/mail/templates', label: 'Templates' },
  { to: '/admin/mail/campaigns', label: 'Campaigns' },
  { to: '/admin/mail/suppressions', label: 'Suppressions' },
];

export default function AdminMailNav() {
  const location = useLocation();
  return (
    <div className="flex flex-wrap gap-2 mb-8">
      {items.map((item) => {
        const active =
          item.match === 'exact'
            ? location.pathname === item.to
            : location.pathname === item.to || location.pathname.startsWith(`${item.to}/`);
        return (
          <Link
            key={item.to}
            to={item.to}
            className={`font-mono text-[10px] uppercase tracking-[0.14em] rounded-sm px-3 py-1.5 border ${
              active
                ? 'bg-slate text-chalk border-slate'
                : 'bg-chalk text-slate/65 border-border-soft hover:border-mint/40'
            }`}
          >
            {item.label}
          </Link>
        );
      })}
      <Link
        to="/admin/mail/campaigns/new"
        className="font-mono text-[10px] uppercase tracking-[0.14em] rounded-sm px-3 py-1.5 border border-mint/30 bg-mint-pale text-mint"
      >
        New campaign
      </Link>
    </div>
  );
}
