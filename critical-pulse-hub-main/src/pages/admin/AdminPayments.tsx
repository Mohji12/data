import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/apiClient';
import { openAuthenticatedExport } from '@/lib/apiBase';

type Tab = 'all' | 'topup' | 'topup_extension' | 'topup_extension_2' | 'registration';

export default function AdminPayments() {
  const [tab, setTab] = useState<Tab>('all');
  const [q, setQ] = useState('');
  const [sortBy, setSortBy] = useState<string>('id');
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');
  const [offset, setOffset] = useState(0);
  const limit = 50;
  const qc = useQueryClient();

  const packageType = tab === 'all' ? undefined : tab;

  const { data, isLoading, error } = useQuery({
    queryKey: ['adminPayments', packageType, q, sortBy, order, offset],
    queryFn: () => {
      const query = new URLSearchParams({ offset: String(offset), limit: String(limit) });
      if (packageType) query.set('package_type', packageType);
      if (q.trim()) query.set('q', q.trim());
      query.set('sort_by', sortBy);
      query.set('order', order);
      return apiClient(`/admin/payments?${query.toString()}`);
    },
  });

  const offlineMut = useMutation({
    mutationFn: (id: number) =>
      apiClient(`/admin/payments/${id}/offline-credit`, {
        method: 'POST',
        body: JSON.stringify({ payment_details: 'Marked offline (React admin)' }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['adminPayments'] }),
  });

  const refundMut = useMutation({
    mutationFn: (id: number) => apiClient(`/admin/payments/${id}/refund`, { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['adminPayments'] }),
  });

  const tabs: { id: Tab; label: string }[] = [
    { id: 'all', label: 'All' },
    { id: 'topup', label: 'Topup' },
    { id: 'topup_extension', label: 'Extension' },
    { id: 'topup_extension_2', label: 'Extension 2' },
    { id: 'registration', label: 'Registration' },
  ];

  const toggleSort = (field: string) => {
    if (sortBy === field) {
      setOrder(order === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setOrder('desc');
    }
    setOffset(0);
  };

  const SortIcon = ({ field }: { field: string }) => {
    if (sortBy !== field) return <span className="opacity-20 ml-1">↕</span>;
    return <span className="ml-1 text-mint">{order === 'asc' ? '↑' : '↓'}</span>;
  };

  return (
    <div className="p-6 lg:p-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="font-display font-bold text-3xl text-slate">Payments</h1>
          <p className="font-mono text-[11px] text-ink-faint mt-1 uppercase tracking-wider">Topups, extensions, registration rows</p>
        </div>
        <button
          type="button"
          onClick={() => {
            const q = packageType ? `?package_type=${packageType}` : '';
            void openAuthenticatedExport(`/admin/payments/export.csv${q}`);
          }}
          className="magnetic bg-slate text-chalk rounded-sm px-5 py-2.5 font-sans text-xs font-semibold hover:bg-slate-light"
        >
          Export CSV
        </button>
      </div>

      <div className="flex flex-col sm:flex-row gap-4 mb-6">
        <div className="flex flex-wrap gap-2">
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => {
                setTab(t.id);
                setOffset(0);
              }}
              className={`rounded-sm px-4 py-2 font-sans text-xs font-medium border transition-colors ${
                tab === t.id ? 'bg-mint-pale border-mint text-slate' : 'bg-chalk border-border-soft text-ink-muted hover:border-border-strong'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="sm:ml-auto w-full sm:w-64">
          <input
            type="text"
            placeholder="Search email, name..."
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setOffset(0);
            }}
            className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm outline-none focus:border-mint/50"
          />
        </div>
      </div>

      {error && <p className="text-red-600 text-sm mb-4">{error instanceof Error ? error.message : 'Error'}</p>}
      {isLoading && <p className="font-mono text-xs text-ink-faint animate-pulse">Loading…</p>}

      {data && (
        <>
          <div className="overflow-x-auto bg-chalk border border-border-soft rounded-sm">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-chalk-cool border-b border-border-soft">
                  <th onClick={() => toggleSort('id')} className="text-left px-4 py-3 font-mono text-[10px] text-ink-faint uppercase cursor-pointer hover:text-ink transition-colors">ID <SortIcon field="id" /></th>
                  <th className="text-left px-4 py-3 font-mono text-[10px] text-ink-faint uppercase">User</th>
                  <th onClick={() => toggleSort('package_type')} className="text-left px-4 py-3 font-mono text-[10px] text-ink-faint uppercase cursor-pointer hover:text-ink transition-colors">Type <SortIcon field="package_type" /></th>
                  <th onClick={() => toggleSort('payment_status')} className="text-left px-4 py-3 font-mono text-[10px] text-ink-faint uppercase cursor-pointer hover:text-ink transition-colors">Status <SortIcon field="payment_status" /></th>
                  <th onClick={() => toggleSort('payment_date')} className="text-left px-4 py-3 font-mono text-[10px] text-ink-faint uppercase cursor-pointer hover:text-ink transition-colors">Date <SortIcon field="payment_date" /></th>
                  <th className="text-right px-4 py-3 font-mono text-[10px] text-ink-faint uppercase">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.items?.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-ink-muted">
                      No rows
                    </td>
                  </tr>
                )}
                {data.items?.map((p: any) => (
                  <tr key={p.id} className="border-b border-border-soft last:border-0 hover:bg-chalk-warm/80">
                    <td className="px-4 py-3 font-mono text-xs text-ink-faint">#{p.id}</td>
                    <td className="px-4 py-3 font-sans text-ink">{p.user_email}</td>
                    <td className="px-4 py-3 font-mono text-xs">{p.package_type || '—'}</td>
                    <td className="px-4 py-3 font-mono text-xs">{p.payment_status || '—'}</td>
                    <td className="px-4 py-3 font-mono text-xs text-ink-muted">{p.payment_date || '—'}</td>
                    <td className="px-4 py-3 text-right space-x-2">
                      <button
                        type="button"
                        disabled={offlineMut.isPending}
                        onClick={() => offlineMut.mutate(p.id)}
                        className="text-xs text-mint font-semibold hover:underline disabled:opacity-50"
                      >
                        Offline credit
                      </button>
                      <button
                        type="button"
                        disabled={refundMut.isPending}
                        onClick={() => refundMut.mutate(p.id)}
                        className="text-xs text-blush font-semibold hover:underline disabled:opacity-50"
                      >
                        Refund
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between mt-4">
            <span className="font-mono text-xs text-ink-faint">Total: {data.total}</span>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - limit))}
                className="px-3 py-1 border border-border-soft rounded-sm text-xs disabled:opacity-40"
              >
                Previous
              </button>
              <button
                type="button"
                disabled={!data.items || offset + limit >= data.total}
                onClick={() => setOffset(offset + limit)}
                className="px-3 py-1 border border-border-soft rounded-sm text-xs disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
