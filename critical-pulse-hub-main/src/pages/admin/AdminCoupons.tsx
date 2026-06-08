import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/apiClient';
import { useIsTechAdmin } from '@/store/authStore';
import { openAuthenticatedExport } from '@/lib/apiBase';
import { toast } from 'sonner';

type CouponRow = { id: number; code: string; status: string; discount_amount: number };

function couponStatusLabel(status: string): string {
  return status === '0' ? 'available' : 'expired';
}

export default function AdminCoupons() {
  const qc = useQueryClient();
  const isTech = useIsTechAdmin();
  const [code, setCode] = useState('');
  const [discount, setDiscount] = useState('0');
  const [genCount, setGenCount] = useState('10');
  const [q, setQ] = useState('');
  const [sortBy, setSortBy] = useState<string>('id');
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');

  const { data: coupons, isLoading, error } = useQuery({
    queryKey: ['adminCoupons', q, sortBy, order],
    queryFn: () => {
      const p = new URLSearchParams();
      if (q.trim()) p.set('q', q.trim());
      p.set('sort_by', sortBy);
      p.set('order', order);
      return apiClient(`/admin/commerce/coupons?${p.toString()}`) as Promise<CouponRow[]>;
    },
  });

  const createMut = useMutation({
    mutationFn: () =>
      apiClient('/admin/commerce/coupons', {
        method: 'POST',
        body: JSON.stringify({ code: code.trim(), status: '0', discount_amount: Number(discount) || 0 }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['adminCoupons'] });
      setCode('');
      setDiscount('0');
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const delMut = useMutation({
    mutationFn: (id: number) => apiClient(`/admin/commerce/coupons/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['adminCoupons'] }),
  });

  const generateMut = useMutation({
    mutationFn: () => {
      const n = Math.min(100, Math.max(1, parseInt(genCount, 10) || 10));
      const qs = new URLSearchParams({ count: String(n), discount_amount: discount });
      return apiClient(`/admin/commerce/coupons/generate?${qs.toString()}`, { method: 'POST' }) as Promise<{ created?: number }>;
    },
    onSuccess: (res) => {
      toast.success(`Generated ${res?.created ?? 0} random coupon code(s) (PHP-style bulk).`);
      void qc.invalidateQueries({ queryKey: ['adminCoupons'] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

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
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="font-display font-bold text-3xl text-slate">Coupons</h1>
          <p className="font-mono text-[11px] text-ink-faint mt-1 uppercase tracking-wider">Create and delete require tech admin</p>
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          <input
            type="text"
            placeholder="Search coupon..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="bg-chalk border border-border-soft rounded-sm py-2 px-3 font-sans text-sm outline-none focus:border-mint/50"
          />
          <button
            type="button"
            onClick={() => void openAuthenticatedExport('/admin/commerce/coupons/export.csv')}
            className="magnetic bg-slate text-chalk rounded-sm px-5 py-2.5 font-sans text-xs font-semibold hover:bg-slate-light"
          >
            Export CSV
          </button>
        </div>
      </div>

      {isTech && (
        <div className="mb-8 flex flex-wrap gap-3 items-end bg-chalk border border-border-soft rounded-sm p-4">
          <div>
            <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">Code</label>
            <input
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-mono text-sm"
              placeholder="SUMMER2026"
            />
          </div>
          <div>
            <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">Discount amount</label>
            <input
              type="number"
              value={discount}
              onChange={(e) => setDiscount(e.target.value)}
              className="bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm w-32"
            />
          </div>
          <button
            type="button"
            disabled={!code.trim() || createMut.isPending}
            onClick={() => createMut.mutate()}
            className="magnetic bg-slate text-chalk rounded-sm px-4 py-2 font-sans text-xs font-semibold hover:bg-slate-light disabled:opacity-50"
          >
            {createMut.isPending ? 'Creating…' : 'Create coupon'}
          </button>
          <div className="w-full sm:w-auto border-t sm:border-t-0 sm:border-l border-border-soft sm:pl-6 pt-3 sm:pt-0 mt-3 sm:mt-0 flex flex-wrap gap-3 items-end">
            <div>
              <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">Bulk generate</label>
              <input
                type="number"
                min={1}
                max={100}
                value={genCount}
                onChange={(e) => setGenCount(e.target.value)}
                className="bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm w-24"
              />
            </div>
            <button
              type="button"
              disabled={generateMut.isPending}
              onClick={() => {
                if (!window.confirm(`Generate ${genCount || 10} random coupon codes?`)) return;
                generateMut.mutate();
              }}
              className="magnetic bg-mint/20 text-slate border border-mint/40 rounded-sm px-4 py-2 font-sans text-xs font-semibold hover:bg-mint/30 disabled:opacity-50"
            >
              {generateMut.isPending ? 'Generating…' : 'Generate random'}
            </button>
          </div>
        </div>
      )}

      {isLoading && <div className="font-mono text-xs text-ink-faint py-12 text-center animate-pulse">Loading…</div>}
      {error && <div className="text-red-600 font-sans text-sm py-6">Failed to load coupons.</div>}

      <div className="bg-chalk border border-border-soft rounded-sm overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="bg-chalk-cool">
              {[
                { id: 'code', label: 'Code' },
                { id: 'discount_amount', label: 'Discount' },
                { label: 'Status' },
                { label: 'Actions' },
              ].map((h) => (
                <th
                  key={h.label}
                  onClick={() => 'id' in h && h.id && toggleSort(h.id)}
                  className={`font-mono text-[11px] text-ink-faint uppercase tracking-[0.1em] text-left px-6 py-3 ${
                    'id' in h ? 'cursor-pointer hover:text-ink transition-colors' : ''
                  }`}
                >
                  {h.label}
                  {'id' in h && <SortIcon field={h.id!} />}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(coupons || []).map((c) => (
              <tr key={c.id} className="border-b border-border-soft hover:bg-ink-ghost">
                <td className="px-6 py-4 font-mono text-sm text-ink font-medium">{c.code}</td>
                <td className="px-6 py-4 font-sans text-sm text-ink-secondary">₹{Number(c.discount_amount ?? 0).toLocaleString()}</td>
                <td className="px-6 py-4">
                  <span
                    className={`font-mono text-[11px] border rounded-sm px-2 py-0.5 ${
                      c.status === '0' ? 'border-mint/30 text-mint' : 'border-blush/30 text-blush'
                    }`}
                  >
                    {couponStatusLabel(c.status)}
                  </span>
                </td>
                <td className="px-6 py-4">
                  {isTech ? (
                    <button
                      type="button"
                      className="text-xs text-blush hover:underline font-sans"
                      disabled={delMut.isPending}
                      onClick={() => {
                        if (window.confirm(`Delete coupon ${c.code}?`)) delMut.mutate(c.id);
                      }}
                    >
                      Delete
                    </button>
                  ) : (
                    <span className="font-mono text-[10px] text-ink-faint">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!isLoading && (coupons || []).length === 0 && (
          <div className="p-12 text-center font-sans text-sm text-ink-muted">No coupons.</div>
        )}
      </div>
    </div>
  );
}
