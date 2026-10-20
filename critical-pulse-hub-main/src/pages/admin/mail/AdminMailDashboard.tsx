import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Mail } from 'lucide-react';
import { apiClient } from '@/lib/apiClient';
import AdminMailNav from './AdminMailNav';
import { campaignStatusClass, campaignStatusLabel, formatIst, type MailDashboard } from './mailTypes';

export default function AdminMailDashboard() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['adminMailDashboard'],
    queryFn: () => apiClient('/admin/mail/dashboard') as Promise<MailDashboard>,
  });

  const stats = [
    { label: 'Campaigns', value: data?.campaigns ?? 0 },
    { label: 'Sent', value: data?.sent ?? 0 },
    { label: 'Scheduled', value: data?.scheduled ?? 0 },
    { label: 'Templates', value: data?.templates ?? 0 },
  ];

  return (
    <div className="p-6 lg:p-8 min-w-0 max-w-full">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-6 mb-6">
        <div>
          <h1 className="font-display font-bold text-3xl text-slate text-center sm:text-left">Email campaigns</h1>
          <p className="font-mono text-[11px] text-slate/55 mt-1.5 uppercase tracking-[0.14em] max-w-xl">
            Templates · schedule IST · send via ZeptoMail · opens from unique clicks
          </p>
        </div>
      </div>
      <AdminMailNav />

      {isError && (
        <div className="text-sm text-blush mb-6 bg-blush/10 border border-blush/25 rounded-sm px-4 py-3">
          {(error as Error).message}
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-10">
        {stats.map((s) => (
          <div key={s.label} className="rounded-sm border border-border-soft bg-chalk px-4 py-4">
            <div className="font-mono text-[10px] text-slate/50 uppercase tracking-wider">{s.label}</div>
            <div className="font-display font-bold text-2xl text-slate mt-1 tabular-nums">{isLoading ? '—' : s.value}</div>
          </div>
        ))}
      </div>

      <section className="rounded-sm border border-border-soft bg-chalk shadow-sm overflow-hidden">
        <div className="border-b border-border-soft bg-chalk-cool/60 px-5 py-3 flex items-center gap-2">
          <div className="w-8 h-8 rounded-sm bg-mint/15 flex items-center justify-center shrink-0">
            <Mail className="w-4 h-4 text-mint" aria-hidden />
          </div>
          <h2 className="font-display font-bold text-lg text-slate leading-tight">Recent campaigns</h2>
        </div>
        <div className="divide-y divide-border-soft">
          {(data?.recent ?? []).length === 0 && !isLoading && (
            <p className="px-5 py-8 text-sm text-slate/55 font-sans">No campaigns yet. Create a template, then send or schedule.</p>
          )}
          {(data?.recent ?? []).map((row) => (
            <Link
              key={row.id}
              to={`/admin/mail/campaigns/${row.id}`}
              className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5 hover:bg-chalk-warm/70"
            >
              <div>
                <div className="font-sans text-sm text-slate font-medium">{row.name}</div>
                <div className="font-mono text-[10px] text-slate/50 mt-0.5">
                  {row.queued_count} recipients · {formatIst(row.scheduled_at || row.sent_at || row.created_at)} IST
                </div>
              </div>
              <span className={`font-mono text-[10px] uppercase tracking-wider border rounded-sm px-2 py-1 ${campaignStatusClass(row.status)}`}>
                {campaignStatusLabel(row)}
              </span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
