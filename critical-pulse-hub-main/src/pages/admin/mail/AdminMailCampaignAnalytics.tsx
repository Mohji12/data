import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { apiClient } from '@/lib/apiClient';
import { useIsTechAdmin } from '@/store/authStore';
import AdminMailNav from './AdminMailNav';
import { campaignStatusClass, campaignStatusLabel, formatIst, type MailAnalytics } from './mailTypes';

export default function AdminMailCampaignAnalytics() {
  const { id } = useParams();
  const campaignId = Number(id);
  const isTech = useIsTechAdmin();
  const qc = useQueryClient();
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['adminMailAnalytics', campaignId],
    queryFn: () => apiClient(`/admin/mail/campaigns/${campaignId}/analytics`) as Promise<MailAnalytics>,
    enabled: Number.isFinite(campaignId),
    refetchInterval: 4000,
  });

  const cancelMut = useMutation({
    mutationFn: () => apiClient(`/admin/mail/campaigns/${campaignId}/cancel`, { method: 'POST' }),
    onSuccess: () => {
      toast.success('Cancelled');
      void qc.invalidateQueries({ queryKey: ['adminMailAnalytics', campaignId] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const camp = data?.campaign;

  return (
    <div className="p-6 lg:p-8 min-w-0 max-w-full">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-6 mb-6">
        <div>
          <h1 className="font-display font-bold text-3xl text-slate">{camp?.name || 'Campaign'}</h1>
          <p className="font-mono text-[11px] text-slate/55 mt-1.5 uppercase tracking-[0.14em]">
            Sent / failed from SMTP · opened = unique click
          </p>
        </div>
        <Link to="/admin/mail/campaigns" className="font-mono text-[11px] uppercase tracking-wider border border-border-soft px-4 py-2.5 rounded-sm">
          All campaigns
        </Link>
      </div>
      <AdminMailNav />

      {isError && <div className="text-sm text-blush mb-6">{(error as Error).message}</div>}
      {isLoading && <p className="text-sm text-slate/55">Loading…</p>}

      {data && camp && (
        <>
          <div className="flex flex-wrap items-center gap-2 mb-6">
            <span className={`font-mono text-[10px] uppercase tracking-wider border rounded-sm px-2 py-1 ${campaignStatusClass(camp.status)}`}>
              {campaignStatusLabel(camp)}
            </span>
            <span className="font-mono text-[11px] text-slate/55">Scheduled {formatIst(camp.scheduled_at)} IST</span>
            {camp.next_wave_at && (
              <span className="font-mono text-[11px] text-slate/55">Next wave {formatIst(camp.next_wave_at)} IST</span>
            )}
            {isTech && !['sent', 'failed', 'cancelled'].includes(camp.status) && (
              <button type="button" className="font-mono text-[10px] uppercase text-blush ml-auto" onClick={() => cancelMut.mutate()}>
                Cancel
              </button>
            )}
          </div>
          <p className="text-sm text-slate/65 mb-6">
            Waves of {camp.send_batch_size ?? 100} emails
            {(camp.send_pause_minutes ?? 0) > 0
              ? ` · ${camp.send_pause_minutes} min pause`
              : ' · no pause'}
            {camp.queued_count
              ? ` · ${camp.accepted_count + camp.failed_count + camp.suppressed_count}/${camp.queued_count} processed`
              : ''}
          </p>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-8">
            {[
              { label: 'Sent', value: data.sent },
              { label: 'Failed', value: data.failed },
              { label: 'Unique opens', value: data.unique_opens },
              { label: 'Open rate', value: `${data.open_rate}%` },
            ].map((s) => (
              <div key={s.label} className="rounded-sm border border-border-soft bg-chalk px-4 py-4">
                <div className="font-mono text-[10px] text-slate/50 uppercase tracking-wider">{s.label}</div>
                <div className="font-display font-bold text-2xl text-slate mt-1 tabular-nums">{s.value}</div>
              </div>
            ))}
          </div>
          <section className="rounded-sm border border-border-soft bg-chalk overflow-hidden">
            <div className="border-b border-border-soft px-5 py-3 font-display font-bold text-slate">Recent clicks</div>
            {(data.recent_clicks ?? []).length === 0 && (
              <p className="px-5 py-6 text-sm text-slate/55">No clicks yet. Opens are counted when a recipient follows a tracked link.</p>
            )}
            {data.recent_clicks.map((c, i) => (
              <div key={`${c.email}-${i}`} className="px-5 py-3 border-b border-border-soft last:border-0 text-sm">
                <div className="font-sans text-slate">{c.email}</div>
                <div className="font-mono text-[11px] text-slate/50 truncate">{c.dest_url}</div>
                <div className="font-mono text-[10px] text-slate/40">{formatIst(c.at)} IST</div>
              </div>
            ))}
          </section>
        </>
      )}
    </div>
  );
}
