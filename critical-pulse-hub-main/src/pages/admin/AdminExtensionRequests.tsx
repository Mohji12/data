import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { apiClient } from '@/lib/apiClient';

type StatusFilter = 'all' | 'pending_offline' | 'payment_failed' | 'abandoned' | 'rejected';

interface ExtensionRequest {
  id: number;
  request_id: string;
  user_id: number;
  user_name: string | null;
  user_email: string | null;
  user_contact: string | null;
  subscription: string | null;
  batch_slug: string | null;
  amount: number;
  currency: string;
  gateway_status: string;
  gateway_order_id: string | null;
  offline_reference: string | null;
  student_note: string | null;
  failure_reason: string | null;
  admin_note: string | null;
  created_at: string | null;
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    created: 'Initiated',
    order_created: 'Checkout opened',
    payment_failed: 'Payment failed',
    pending_offline: 'Pending offline',
    rejected: 'Rejected',
    paid: 'Paid',
  };
  return map[status] || status;
}

function statusClass(status: string): string {
  if (status === 'pending_offline') return 'bg-mint/10 text-mint border-mint/20';
  if (status === 'payment_failed') return 'bg-blush/10 text-blush border-blush/20';
  if (status === 'rejected') return 'bg-ink-ghost text-ink-faint border-border-soft';
  return 'bg-chalk-cool text-ink-muted border-border-soft';
}

export default function AdminExtensionRequests() {
  const qc = useQueryClient();
  const [status, setStatus] = useState<StatusFilter>('all');
  const [q, setQ] = useState('');
  const [offset, setOffset] = useState(0);
  const [actionRow, setActionRow] = useState<ExtensionRequest | null>(null);
  const [actionType, setActionType] = useState<'approve' | 'reject' | null>(null);
  const [adminNote, setAdminNote] = useState('');
  const limit = 50;

  const { data, isLoading, error } = useQuery({
    queryKey: ['adminExtensionRequests', status, q, offset],
    queryFn: () => {
      const query = new URLSearchParams({ offset: String(offset), limit: String(limit) });
      if (status !== 'all') query.set('status', status);
      if (q.trim()) query.set('q', q.trim());
      return apiClient(`/admin/extension-requests?${query.toString()}`);
    },
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ['adminExtensionRequests'] });

  const approveMut = useMutation({
    mutationFn: ({ requestId, note }: { requestId: string; note?: string }) =>
      apiClient(`/admin/extension-requests/${encodeURIComponent(requestId)}/approve`, {
        method: 'POST',
        body: JSON.stringify({ admin_note: note || undefined, payment_details: note || undefined }),
      }),
    onSuccess: (res: { message?: string; extended_end_at?: string }) => {
      toast.success(res?.message || 'Extension approved');
      setActionRow(null);
      setActionType(null);
      setAdminNote('');
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const rejectMut = useMutation({
    mutationFn: ({ requestId, note }: { requestId: string; note?: string }) =>
      apiClient(`/admin/extension-requests/${encodeURIComponent(requestId)}/reject`, {
        method: 'POST',
        body: JSON.stringify({ admin_note: note || undefined }),
      }),
    onSuccess: () => {
      toast.success('Extension request rejected');
      setActionRow(null);
      setActionType(null);
      setAdminNote('');
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const syncMut = useMutation({
    mutationFn: (requestId: string) =>
      apiClient(`/admin/extension-requests/${encodeURIComponent(requestId)}/sync-razorpay`, {
        method: 'POST',
        body: '{}',
      }),
    onSuccess: (res: { message?: string }) => {
      toast.success(res?.message || 'Synced from Razorpay');
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const tabs: { id: StatusFilter; label: string }[] = [
    { id: 'all', label: 'All' },
    { id: 'pending_offline', label: 'Pending offline' },
    { id: 'payment_failed', label: 'Payment failed' },
    { id: 'abandoned', label: 'Abandoned' },
    { id: 'rejected', label: 'Rejected' },
  ];

  const closeModal = () => {
    setActionRow(null);
    setActionType(null);
    setAdminNote('');
  };

  return (
    <div className="p-6 lg:p-8">
      <div className="mb-8">
        <h1 className="font-display font-bold text-3xl text-slate">Extension requests</h1>
        <p className="font-mono text-[11px] text-ink-faint mt-1 uppercase tracking-wider">
          Failed or offline extension payments awaiting admin approval
        </p>
      </div>

      <div className="flex flex-col sm:flex-row gap-4 mb-6">
        <div className="flex flex-wrap gap-2">
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => {
                setStatus(t.id);
                setOffset(0);
              }}
              className={`rounded-sm px-4 py-2 font-sans text-xs font-medium border transition-colors ${
                status === t.id ? 'bg-mint-pale border-mint text-slate' : 'bg-chalk border-border-soft text-ink-muted hover:border-border-strong'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="sm:ml-auto w-full sm:w-64">
          <input
            type="text"
            placeholder="Search name, email..."
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
                  <th className="text-left px-4 py-3 font-mono text-[10px] text-ink-faint uppercase">Student</th>
                  <th className="text-left px-4 py-3 font-mono text-[10px] text-ink-faint uppercase">Batch</th>
                  <th className="text-left px-4 py-3 font-mono text-[10px] text-ink-faint uppercase">Amount</th>
                  <th className="text-left px-4 py-3 font-mono text-[10px] text-ink-faint uppercase">Status</th>
                  <th className="text-left px-4 py-3 font-mono text-[10px] text-ink-faint uppercase">Offline ref</th>
                  <th className="text-left px-4 py-3 font-mono text-[10px] text-ink-faint uppercase">Attempted</th>
                  <th className="text-right px-4 py-3 font-mono text-[10px] text-ink-faint uppercase">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.items?.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-ink-muted">
                      No extension requests
                    </td>
                  </tr>
                )}
                {data.items?.map((row: ExtensionRequest) => (
                  <tr key={row.request_id} className="border-b border-border-soft last:border-0 hover:bg-chalk-warm/80 align-top">
                    <td className="px-4 py-3">
                      <div className="font-sans text-ink">{row.user_name || '—'}</div>
                      <div className="font-mono text-xs text-ink-muted">{row.user_email}</div>
                      {row.user_contact && <div className="font-mono text-[10px] text-ink-faint">{row.user_contact}</div>}
                    </td>
                    <td className="px-4 py-3 font-sans text-xs text-ink-muted max-w-[160px]">{row.subscription || row.batch_slug || '—'}</td>
                    <td className="px-4 py-3 font-mono text-xs">₹{row.amount.toLocaleString()}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-mono border ${statusClass(row.gateway_status)}`}>
                        {statusLabel(row.gateway_status)}
                      </span>
                      {row.failure_reason && (
                        <div className="text-[10px] text-ink-faint mt-1 max-w-[180px]">{row.failure_reason}</div>
                      )}
                      {row.student_note && (
                        <div className="text-[10px] text-ink-muted mt-1 max-w-[180px] italic">{row.student_note}</div>
                      )}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs">{row.offline_reference || '—'}</td>
                    <td className="px-4 py-3 font-mono text-[10px] text-ink-muted">
                      {row.created_at ? new Date(row.created_at).toLocaleString('en-IN') : '—'}
                      {row.gateway_order_id && (
                        <div className="text-[9px] text-ink-faint mt-1 break-all">RZP: {row.gateway_order_id}</div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right space-y-1">
                      {row.gateway_status !== 'rejected' && (
                        <>
                          <button
                            type="button"
                            disabled={approveMut.isPending}
                            onClick={() => {
                              setActionRow(row);
                              setActionType('approve');
                            }}
                            className="block ml-auto text-xs text-mint font-semibold hover:underline disabled:opacity-50"
                          >
                            Approve
                          </button>
                          <button
                            type="button"
                            disabled={syncMut.isPending}
                            onClick={() => syncMut.mutate(row.request_id)}
                            className="block ml-auto text-xs text-slate font-semibold hover:underline disabled:opacity-50"
                          >
                            Sync Razorpay
                          </button>
                          <button
                            type="button"
                            disabled={rejectMut.isPending}
                            onClick={() => {
                              setActionRow(row);
                              setActionType('reject');
                            }}
                            className="block ml-auto text-xs text-blush font-semibold hover:underline disabled:opacity-50"
                          >
                            Reject
                          </button>
                        </>
                      )}
                      {row.gateway_status === 'rejected' && row.admin_note && (
                        <div className="text-[10px] text-ink-faint text-right">{row.admin_note}</div>
                      )}
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

      {actionRow && actionType && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4 backdrop-blur-sm">
          <div className="w-full max-w-md bg-chalk border border-border-soft rounded-sm shadow-2xl p-6">
            <h2 className="font-display font-bold text-lg text-slate mb-1">
              {actionType === 'approve' ? 'Approve extension' : 'Reject extension'}
            </h2>
            <p className="font-sans text-xs text-ink-muted mb-4">
              {actionRow.user_email} — ₹{actionRow.amount.toLocaleString()}
            </p>
            <label className="block font-mono text-[10px] text-ink-faint uppercase tracking-wider mb-1">
              {actionType === 'approve' ? 'Payment note (optional)' : 'Rejection reason (optional)'}
            </label>
            <textarea
              value={adminNote}
              onChange={(e) => setAdminNote(e.target.value)}
              rows={3}
              className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm outline-none resize-none mb-4"
            />
            <div className="flex justify-end gap-3">
              <button type="button" onClick={closeModal} className="px-4 py-2 text-xs text-ink-muted">
                Cancel
              </button>
              <button
                type="button"
                disabled={approveMut.isPending || rejectMut.isPending}
                onClick={() => {
                  if (actionType === 'approve') {
                    approveMut.mutate({ requestId: actionRow.request_id, note: adminNote || undefined });
                  } else {
                    rejectMut.mutate({ requestId: actionRow.request_id, note: adminNote || undefined });
                  }
                }}
                className={`px-5 py-2 rounded-sm text-xs font-bold text-chalk ${
                  actionType === 'approve' ? 'bg-mint text-slate' : 'bg-blush'
                } disabled:opacity-50`}
              >
                {actionType === 'approve' ? 'Confirm approve' : 'Confirm reject'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
