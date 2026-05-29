import { Link, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { useOdometer } from '@/hooks/useOdometer';
import { PlayCircle, ClipboardCheck, BookOpen, ArrowUpRight, AlertTriangle } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/apiClient';
import { useEffect } from 'react';

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

  return (
    <div>
      <div className="bg-chalk border-b border-border-soft px-6 lg:px-8 py-6">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center">
          <h1 className="font-display font-bold text-3xl text-slate">Good morning, {summary?.name || user?.name || 'Doctor'}.</h1>
        </div>
        
        {(!summary?.video?.enabled || !summary?.mock_test?.enabled || !summary?.certificate?.enabled) && (
          <div className="bg-amber-pale border border-amber/30 rounded-sm px-5 py-3 mt-3 flex items-center gap-3">
            <AlertTriangle size={15} className="text-amber shrink-0" />
            <span className="font-sans text-sm text-amber">
              Limited access based on subscription: {summary?.mock_test?.reason || summary?.video?.reason || summary?.certificate?.reason || 'Check your package.'}
            </span>
            {summary?.extension?.enabled && (
              <Link to="/dashboard/extend-subscription" className="font-sans text-sm text-mint ml-auto">Extend →</Link>
            )}
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
                  sub: `${summary?.extension?.days_to_expiry ?? 0} days left · ${summary?.extension?.currency_name || 'INR'} ${summary?.extension?.estimated_amount ?? 0}`,
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
