import { Link, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { useOdometer } from '@/hooks/useOdometer';
import { PlayCircle, ClipboardCheck, BookOpen, ArrowUpRight, Calendar } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/apiClient';

function formatBatchDate(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleDateString('en-IN', {
    timeZone: 'Asia/Kolkata',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
}

export default function Dashboard() {
  const { user } = useAuthStore();
  const navigate = useNavigate();

  const { data: summary, isLoading, error } = useQuery({
    queryKey: ['dashboardSummary'],
    queryFn: () => apiClient('/dashboard/summary'),
    enabled: !!user?.id,
  });

  // Since metrics are not fully aggregated in the API yet, we default to 0.
  const videosWatched = useOdometer(0);
  const quizScore = useOdometer(0);
  const hoursSpent = useOdometer(0);
  const testsCompleted = useOdometer(0);

  if (isLoading) return <div className="p-8 font-mono text-sm text-ink-faint">Loading real-time dashboard...</div>;
  if (error) return <div className="p-8 font-mono text-sm text-red-500">Failed to connect to real-time data API.</div>;

  const batchAccess = summary?.batch_access;
  const batchEndLabel = batchAccess?.is_extended ? 'Extended access until' : 'Batch access until';

  return (
    <div>
      <div className="bg-chalk border-b border-border-soft px-6 lg:px-8 py-6">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
          <div>
            <h1 className="font-display font-bold text-3xl text-slate">Good morning, {summary?.name || user?.name || 'Doctor'}.</h1>
            {batchAccess?.end_at && (
              <p className="font-sans text-sm text-ink-muted mt-2 flex items-center gap-2 flex-wrap">
                <Calendar size={14} className="text-ink-faint shrink-0" />
                <span>
                  <strong className="text-slate">{batchEndLabel}:</strong> {formatBatchDate(batchAccess.end_at)}
                  {batchAccess.is_extended && batchAccess.original_end_at && (
                    <span className="text-ink-faint">
                      {' '}(original end: {formatBatchDate(batchAccess.original_end_at)})
                    </span>
                  )}
                  {!batchAccess.is_extended && batchAccess.end_at_if_extended && batchAccess.extension_months && (
                    <span className="text-mint">
                      {' '}· after extension: {formatBatchDate(batchAccess.end_at_if_extended)}
                    </span>
                  )}
                </span>
              </p>
            )}
          </div>
        </div>
        
        {summary?.extension?.enabled && (
          <div className="bg-mint-pale border border-mint/30 rounded-sm px-5 py-4 mt-4 flex flex-col sm:flex-row sm:items-center gap-3">
            <p className="font-sans text-sm text-slate flex-1">
              {summary.extension.headline || (
                <>
                  Extend your access by {summary.extension.extension_months} months —{' '}
                  ₹{summary.extension.payment_amount_inr?.toLocaleString() ?? summary.extension.estimated_amount}
                </>
              )}
            </p>
            <Link
              to="/dashboard/extend-subscription"
              className="shrink-0 inline-flex items-center justify-center bg-slate text-chalk rounded-sm px-4 py-2 font-sans text-sm font-semibold hover:bg-slate-light"
            >
              Pay & extend access →
            </Link>
          </div>
        )}
      </div>

      <div className="p-6 lg:p-8">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-8">
          {[
            { icon: PlayCircle, value: videosWatched, label: 'Videos Watched' },
            { icon: ClipboardCheck, value: quizScore, label: 'Avg Quiz Score' },
            { icon: BookOpen, value: hoursSpent, label: 'Hours Spent' },
            { icon: ClipboardCheck, value: testsCompleted, label: 'Tests Done' },
          ].map((s, i) => {
            const Icon = s.icon;
            return (
              <div key={i} className="bg-chalk border border-border-soft rounded-sm p-6 hover:shadow-sm hover:-translate-y-0.5 transition-all">
                <Icon size={16} className="text-ink-faint" />
                <div className="font-display font-black text-5xl text-slate leading-none mt-3">{s.value}</div>
                <div className="font-mono text-xs text-ink-faint mt-2">{s.label}</div>
              </div>
            );
          })}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {[
            // Dynamically show blocks based on real API permissions!
            ...(summary?.video?.enabled ? [{ title: 'Watch Videos', sub: 'Access your batch folders', to: '/dashboard/videos' }] : []),
            ...(summary?.mock_test?.enabled ? [{ title: 'Mock Tests', sub: 'Practice real exam patterns', to: '/dashboard/quiz' }] : []),
            ...(summary?.extension?.enabled
              ? [{
                  title: 'Extend Subscription',
                  sub: summary?.extension?.headline
                    ? 'Continue access after the official batch end date'
                    : `${summary?.extension?.days_to_expiry ?? 0} days left · ₹${summary?.extension?.payment_amount_inr ?? summary?.extension?.estimated_amount ?? 0}`,
                  to: '/dashboard/extend-subscription',
                }]
              : []),
            ...(summary?.certificate?.enabled
              ? [{ title: 'Download Certificate', sub: 'Get your course completion certificate', to: '/dashboard/certificate' }]
              : []),
            { title: 'Update Profile', sub: 'Manage your professional details', to: '/dashboard/profile' },
          ].map((item) => (
            <Link key={item.title} to={item.to} className="bg-chalk border border-border-soft rounded-sm p-8 hover:border-mint/30 hover:shadow-mint transition-all group cursor-pointer">
              <div className="font-display font-bold text-xl text-slate">{item.title}</div>
              <div className="font-sans text-sm text-ink-muted mt-2">{item.sub}</div>
              <ArrowUpRight size={16} className="text-ink-faint group-hover:text-mint mt-8 transition-colors" />
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
