import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { apiClient } from '@/lib/apiClient';
import { useIsTechAdmin } from '@/store/authStore';
import AdminMailNav from './AdminMailNav';
import { campaignStatusClass, campaignStatusLabel, formatIst, type MailCampaign } from './mailTypes';

export default function AdminMailCampaigns() {
  const isTech = useIsTechAdmin();
  const qc = useQueryClient();
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['adminMailCampaigns'],
    queryFn: () => apiClient('/admin/mail/campaigns') as Promise<MailCampaign[]>,
  });

  const cancelMut = useMutation({
    mutationFn: (id: number) => apiClient(`/admin/mail/campaigns/${id}/cancel`, { method: 'POST' }),
    onSuccess: () => {
      toast.success('Campaign cancelled');
      void qc.invalidateQueries({ queryKey: ['adminMailCampaigns'] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const list = data ?? [];

  return (
    <div className="p-6 lg:p-8 min-w-0 max-w-full">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-6 mb-6">
        <div>
          <h1 className="font-display font-bold text-3xl text-slate">Campaigns</h1>
          <p className="font-mono text-[11px] text-slate/55 mt-1.5 uppercase tracking-[0.14em]">
            Status · sent / failed · click opens
          </p>
        </div>
        {isTech && (
          <Link
            to="/admin/mail/campaigns/new"
            className="font-mono text-[11px] uppercase tracking-wider bg-slate text-chalk px-4 py-2.5 rounded-sm"
          >
            New campaign
          </Link>
        )}
      </div>
      <AdminMailNav />
      {isError && <div className="text-sm text-blush mb-6">{(error as Error).message}</div>}
      {isLoading && <p className="text-sm text-slate/55">Loading…</p>}

      <div className="rounded-sm border border-border-soft bg-chalk overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr className="font-mono text-[10px] uppercase tracking-wider text-slate/50 border-b border-border-soft">
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Queued</th>
              <th className="px-4 py-3">Sent</th>
              <th className="px-4 py-3">Failed</th>
              <th className="px-4 py-3">When (IST)</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {list.map((row) => (
              <tr key={row.id} className="border-b border-border-soft last:border-0">
                <td className="px-4 py-3 font-sans text-sm">
                  <Link to={`/admin/mail/campaigns/${row.id}`} className="text-slate hover:text-mint font-medium">
                    {row.name}
                  </Link>
                </td>
                <td className="px-4 py-3">
                  <span className={`font-mono text-[10px] uppercase tracking-wider border rounded-sm px-2 py-1 ${campaignStatusClass(row.status)}`}>
                    {campaignStatusLabel(row)}
                  </span>
                </td>
                <td className="px-4 py-3 font-mono text-sm tabular-nums">{row.queued_count}</td>
                <td className="px-4 py-3 font-mono text-sm tabular-nums">{row.accepted_count}</td>
                <td className="px-4 py-3 font-mono text-sm tabular-nums">{row.failed_count}</td>
                <td className="px-4 py-3 font-mono text-[11px] text-slate/60">{formatIst(row.scheduled_at || row.sent_at || row.created_at)}</td>
                <td className="px-4 py-3 text-right">
                  {isTech && !['sent', 'failed', 'cancelled'].includes(row.status) && (
                    <button
                      type="button"
                      className="font-mono text-[10px] uppercase text-blush"
                      onClick={() => cancelMut.mutate(row.id)}
                    >
                      Cancel
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {list.length === 0 && !isLoading && <p className="px-5 py-8 text-sm text-slate/55">No campaigns yet.</p>}
      </div>
    </div>
  );
}
