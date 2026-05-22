import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { formatDistanceToNow } from 'date-fns';
import { apiClient } from '@/lib/apiClient';
import { openAuthenticatedExport } from '@/lib/apiBase';
import { Download, Search } from 'lucide-react';
import { toast } from 'sonner';

type Row = {
  id: number;
  user_id: number;
  user_name: string;
  email: string | null;
  contact_number: string | null;
  activity: string | null;
  activity_datetime: string | null;
};

type Page = { total: number; items: Row[] };

const POLL_MS = 15_000;

export default function AdminLoginActivity() {
  const [q, setQ] = useState('');
  const [onDate, setOnDate] = useState('');
  const [sortBy, setSortBy] = useState<string>('id');
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');

  const qs = new URLSearchParams({ limit: '100', offset: '0' });
  if (q.trim()) qs.set('q', q.trim());
  if (onDate) qs.set('on_date', onDate);
  qs.set('sort_by', sortBy);
  qs.set('order', order);

  const { data, isLoading, error, isFetching, dataUpdatedAt } = useQuery({
    queryKey: ['adminLoginActivity', q, onDate, sortBy, order],
    queryFn: () => apiClient(`/admin/misc/login-activity?${qs.toString()}`) as Promise<Page>,
    refetchInterval: POLL_MS,
    refetchIntervalInBackground: true,
  });

  const rows = data?.items ?? [];
  const total = data?.total ?? 0;

  const toggleSort = (field: string) => {
    if (sortBy === field) {
      setOrder(order === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setOrder('desc');
    }
  };

  const SortIcon = ({ field }: { field: string }) => {
    if (sortBy !== field) return <span className="opacity-20 ml-1">↕</span>;
    return <span className="ml-1 text-mint">{order === 'asc' ? '↑' : '↓'}</span>;
  };

  return (
    <div className="p-6 lg:p-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="font-display font-bold text-3xl text-slate">Login Activity</h1>
          <p className="font-mono text-[10px] text-ink-faint mt-1 uppercase tracking-wider">
            Live from <code className="text-ink-muted">login_activity</code> · refresh every {POLL_MS / 1000}s
            {dataUpdatedAt ? ` · last updated ${formatDistanceToNow(dataUpdatedAt, { addSuffix: true })}` : ''}
            {isFetching ? ' · updating…' : ''}
          </p>
        </div>
        <button
          type="button"
          onClick={() =>
            void openAuthenticatedExport(`/admin/misc/login-activity/export.csv`).catch((e) =>
              toast.error(e instanceof Error ? e.message : 'Export failed'),
            )
          }
          className="inline-flex items-center gap-2 magnetic bg-slate text-chalk rounded-sm px-5 py-2.5 font-sans text-xs font-semibold hover:bg-slate-light shrink-0"
        >
          <Download size={14} />
          Export CSV
        </button>
      </div>

      <div className="flex flex-col sm:flex-row gap-3 mb-6 max-w-3xl">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" size={14} />
          <input
            type="search"
            placeholder="Search name, email, phone…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="w-full bg-chalk border border-border-soft rounded-sm py-2 pl-9 pr-3 font-sans text-sm outline-none focus:border-mint/50"
          />
        </div>
        <div>
          <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">Date</label>
          <input
            type="date"
            value={onDate}
            onChange={(e) => setOnDate(e.target.value)}
            className="bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm"
          />
        </div>
      </div>

      {isLoading && <p className="font-mono text-xs text-ink-faint animate-pulse">Loading activity…</p>}
      {error && (
        <p className="text-red-600 text-sm mb-4">{error instanceof Error ? error.message : 'Failed to load'}</p>
      )}

      <div className="bg-chalk border border-border-soft rounded-sm overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="bg-chalk-cool">
              {[
                { id: 'user_name', label: 'User' },
                { id: 'email', label: 'Email' },
                { id: 'contact_number', label: 'Phone' },
                { id: 'activity', label: 'Activity' },
                { id: 'activity_datetime', label: 'Time' },
              ].map((h) => (
                <th
                  key={h.label}
                  onClick={() => toggleSort(h.id)}
                  className="font-mono text-[11px] text-ink-faint uppercase tracking-[0.1em] text-left px-6 py-3 cursor-pointer hover:text-ink transition-colors"
                >
                  {h.label}
                  <SortIcon field={h.id} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {!isLoading && rows.length === 0 && (
              <tr>
                <td colSpan={5} className="px-6 py-12 text-center font-sans text-sm text-ink-muted">
                  No login activity found.
                </td>
              </tr>
            )}
            {rows.map((a) => {
              const dt = a.activity_datetime ? new Date(a.activity_datetime) : null;
              const rel = dt && !Number.isNaN(dt.getTime()) ? formatDistanceToNow(dt, { addSuffix: true }) : '—';
              const abs = dt && !Number.isNaN(dt.getTime()) ? dt.toLocaleString() : '';
              const act = (a.activity || '').trim();
              const badge =
                act.toLowerCase() === 'login'
                  ? 'bg-mint-pale text-mint border-mint/30'
                  : act.toLowerCase() === 'logout'
                    ? 'bg-blush/10 text-blush border-blush/30'
                    : 'bg-chalk-cool text-ink-muted border-border-soft';
              return (
                <tr key={a.id} className="border-b border-border-soft hover:bg-ink-ghost">
                  <td className="px-6 py-4 font-sans text-sm text-ink">{a.user_name}</td>
                  <td className="px-6 py-4 font-mono text-[11px] text-ink-faint select-all">{a.email ?? '—'}</td>
                  <td className="px-6 py-4 font-mono text-[11px] text-ink-faint">{a.contact_number ?? '—'}</td>
                  <td className="px-6 py-4">
                    <span className={`font-mono text-[10px] uppercase border rounded-sm px-2 py-0.5 ${badge}`}>
                      {act || '—'}
                    </span>
                  </td>
                  <td className="px-6 py-4 font-mono text-xs text-ink-faint" title={abs}>
                    {rel}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {total > rows.length && (
        <p className="font-mono text-[10px] text-ink-faint mt-3">
          Showing {rows.length} of {total} rows (increase limit in UI if needed).
        </p>
      )}
    </div>
  );
}
