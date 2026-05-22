import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/apiClient';

export default function AdminDashboard() {
  const { data: summary, isLoading } = useQuery({
    queryKey: ['adminSummary'],
    queryFn: () => apiClient('/admin/misc/summary'),
  });

  const totalUsers = String(summary?.total_users ?? 0);
  const activeUsers = String(summary?.active_users ?? 0);
  const revenueValue = Number(summary?.revenue_estimated ?? 0);
  const revenue = new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(revenueValue);
  const totalVideos = String(summary?.total_videos ?? 0);
  const pendingQuestions = String(summary?.pending_video_questions ?? 0);

  const recentUsers = summary?.recent_users || [];

  return (
    <div className="p-6 lg:p-8">
      <h1 className="font-display font-bold text-3xl text-slate mb-8">Admin Dashboard</h1>
      
      {isLoading && <div className="font-mono text-xs text-ink-faint mb-8 animate-pulse">Computing system metrics...</div>}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-8">
        {[
          { v: totalUsers, l: 'Total Users' }, 
          { v: activeUsers, l: 'Active Users' }, 
          { v: revenue, l: 'Revenue (INR)' }, 
          { v: totalVideos, l: 'Total Videos' },
        ].map((s, i) => (
          <div key={i} className="bg-white border border-border-soft rounded-sm p-6 shadow-sm">
            <div className="font-display font-black text-4xl text-slate leading-none">{s.v}</div>
            <div className="font-mono text-[11px] text-ink-faint mt-2 uppercase tracking-widest">{s.l}</div>
          </div>
        ))}
      </div>

      <div className="mb-8 flex flex-wrap gap-3">
        <Link
          to="/admin/content/video-questions"
          className="inline-flex items-center gap-2 bg-amber-pale border border-amber/30 rounded-sm px-4 py-3 font-sans text-sm text-slate hover:border-amber/50 transition-colors"
        >
          <span className="font-display font-bold text-2xl text-amber tabular-nums">{pendingQuestions}</span>
          <span>Video questions pending moderation</span>
        </Link>
        <Link
          to="/admin/auditorium"
          className="inline-flex items-center rounded-sm border border-border-soft bg-chalk px-4 py-3 font-sans text-sm text-ink-secondary hover:border-mint/30 transition-colors"
        >
          Auditorium link
        </Link>
      </div>

      <div className="bg-white border border-border-soft rounded-sm shadow-sm">
        <div className="p-6 border-b border-border-soft flex items-center justify-between">
          <h2 className="font-display font-bold text-xl text-slate">Recent Registrations</h2>
          <span className="font-mono text-[10px] text-mint bg-mint-pale px-2 py-0.5 rounded-full uppercase tracking-tighter">Live Monitor</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="bg-chalk-cool border-b border-border-soft">
                <th className="font-mono text-[10px] text-ink-faint uppercase font-semibold text-left px-6 py-3 whitespace-nowrap">ID</th>
                <th className="font-mono text-[10px] text-ink-faint uppercase font-semibold text-left px-6 py-3 whitespace-nowrap">Name</th>
                <th className="font-mono text-[10px] text-ink-faint uppercase font-semibold text-left px-6 py-3 whitespace-nowrap">Email</th>
                <th className="font-mono text-[10px] text-ink-faint uppercase font-semibold text-left px-6 py-3 whitespace-nowrap">Course</th>
                <th className="font-mono text-[10px] text-ink-faint uppercase font-semibold text-left px-6 py-3 whitespace-nowrap">Status</th>
              </tr>
            </thead>
            <tbody>
              {recentUsers.length === 0 && !isLoading && (
                <tr><td colSpan={5} className="text-center py-8 text-ink-muted font-sans text-sm">No recent signups found.</td></tr>
              )}
              {recentUsers.map((u: any) => (
                <tr key={u.id} className="border-b border-border-soft last:border-0 hover:bg-slate-50 transition-colors">
                  <td className="px-6 py-4 font-mono text-[11px] text-ink-faint">#{u.id}</td>
                  <td className="px-6 py-4 font-sans text-sm font-medium text-slate">{u.name || 'Anonymous'}</td>
                  <td className="px-6 py-4 font-mono text-[11px] text-ink-muted">{u.email}</td>
                  <td className="px-6 py-4 font-mono text-[11px] text-ink-muted truncate max-w-[150px]">{u.subscription || 'N/A'}</td>
                  <td className="px-6 py-4">
                    <span className={`font-mono text-[9px] uppercase tracking-wider px-2 py-1 rounded-sm border ${u.approve === '1' ? 'border-mint/30 text-mint' : 'border-amber/30 text-amber'}`}>
                      {u.approve === '1' ? 'Approved' : 'Pending'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
