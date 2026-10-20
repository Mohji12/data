import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { apiClient } from '@/lib/apiClient';
import { useIsTechAdmin } from '@/store/authStore';
import AdminMailNav from './AdminMailNav';
import { formatIst, type MailSuppressionList } from './mailTypes';

const field = 'w-full bg-chalk-warm border border-border-soft rounded-sm py-2.5 px-3 font-sans text-sm text-slate focus:outline-none focus:ring-2 focus:ring-mint/25';

export default function AdminMailSuppressions() {
  const isTech = useIsTechAdmin();
  const qc = useQueryClient();
  const [q, setQ] = useState('');
  const [reason, setReason] = useState('');
  const [page, setPage] = useState(1);
  const [pasted, setPasted] = useState('');

  const list = useQuery({
    queryKey: ['adminMailSuppressions', q, reason, page],
    queryFn: () =>
      apiClient(
        `/admin/mail/suppressions?q=${encodeURIComponent(q)}&reason=${encodeURIComponent(reason)}&page=${page}&page_size=25`,
      ) as Promise<MailSuppressionList>,
  });

  const addMut = useMutation({
    mutationFn: () =>
      apiClient('/admin/mail/suppressions', {
        method: 'POST',
        body: JSON.stringify({ pasted, reason: 'manual_block' }),
      }) as Promise<{ added: number; invalid_count: number }>,
    onSuccess: (res) => {
      toast.success(`Blocked ${res.added} address${res.added === 1 ? '' : 'es'}`);
      setPasted('');
      void qc.invalidateQueries({ queryKey: ['adminMailSuppressions'] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const delMut = useMutation({
    mutationFn: (id: number) => apiClient(`/admin/mail/suppressions/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      toast.success('Removed');
      void qc.invalidateQueries({ queryKey: ['adminMailSuppressions'] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const data = list.data;
  const pages = Math.max(1, Math.ceil((data?.total ?? 0) / 25));

  return (
    <div className="p-6 lg:p-8 min-w-0 max-w-full">
      <div className="mb-6">
        <h1 className="font-display font-bold text-3xl text-slate">Suppressions</h1>
        <p className="font-mono text-[11px] text-slate/55 mt-1.5 uppercase tracking-[0.14em]">
          Unsubscribes · bounces · complaints · manual blocks
        </p>
      </div>
      <AdminMailNav />

      {isTech && (
        <section className="rounded-sm border border-border-soft bg-chalk p-5 space-y-3 max-w-2xl mb-6">
          <span className="font-mono text-[10px] text-slate/65 uppercase tracking-wider block">Bulk block emails</span>
          <textarea className={`${field} min-h-[100px] font-mono text-xs`} value={pasted} onChange={(e) => setPasted(e.target.value)} placeholder="one@example.com" />
          <button
            type="button"
            className="font-mono text-[11px] uppercase bg-slate text-chalk px-4 py-2.5 rounded-sm disabled:opacity-40"
            disabled={!pasted.trim() || addMut.isPending}
            onClick={() => addMut.mutate()}
          >
            Block these
          </button>
        </section>
      )}

      <div className="flex flex-wrap gap-3 mb-4 max-w-2xl">
        <input className={field} placeholder="Search email" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
        <select className={field} value={reason} onChange={(e) => { setReason(e.target.value); setPage(1); }}>
          <option value="">All reasons</option>
          {(data?.reasons ?? ['unsubscribe', 'hard_bounce', 'soft_bounce', 'complaint', 'invalid', 'disposable', 'manual_block']).map((r) => (
            <option key={r} value={r}>{r.replace(/_/g, ' ')}</option>
          ))}
        </select>
      </div>

      {list.isError && <div className="text-sm text-blush mb-4">{(list.error as Error).message}</div>}

      <div className="rounded-sm border border-border-soft bg-chalk overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr className="font-mono text-[10px] uppercase tracking-wider text-slate/50 border-b border-border-soft">
              <th className="px-4 py-3">Email</th>
              <th className="px-4 py-3">Reason</th>
              <th className="px-4 py-3">Source</th>
              <th className="px-4 py-3">Detail</th>
              <th className="px-4 py-3">When</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {(data?.items ?? []).map((row) => (
              <tr key={row.id} className="border-b border-border-soft last:border-0">
                <td className="px-4 py-3 font-mono text-xs">{row.email}</td>
                <td className="px-4 py-3 font-mono text-[10px] uppercase">{row.reason.replace(/_/g, ' ')}</td>
                <td className="px-4 py-3 font-mono text-[11px] text-slate/60">{row.source}</td>
                <td className="px-4 py-3 font-mono text-[11px] text-slate/50 max-w-xs truncate">{row.diagnostic || (row.bounce_count ? `${row.bounce_count} soft` : '—')}</td>
                <td className="px-4 py-3 font-mono text-[11px] text-slate/60">{formatIst(row.last_event_at || row.created_at)}</td>
                <td className="px-4 py-3 text-right">
                  {isTech && (
                    <button type="button" className="font-mono text-[10px] uppercase text-blush" onClick={() => delMut.mutate(row.id)}>
                      Remove
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {(data?.items ?? []).length === 0 && !list.isLoading && <p className="px-5 py-8 text-sm text-slate/55">No suppressed addresses.</p>}
      </div>
      <div className="flex gap-2 mt-4 font-mono text-[11px]">
        <button type="button" className="border border-border-soft px-3 py-1.5 rounded-sm disabled:opacity-40" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Prev</button>
        <span className="py-1.5 text-slate/55">Page {page} / {pages}</span>
        <button type="button" className="border border-border-soft px-3 py-1.5 rounded-sm disabled:opacity-40" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>Next</button>
      </div>
    </div>
  );
}
