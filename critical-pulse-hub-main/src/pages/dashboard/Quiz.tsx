import { Link } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/apiClient';

export default function Quiz() {
  const { user } = useAuthStore();
  const { data: quizzes, isLoading, error } = useQuery({
    queryKey: ['exams', user?.id],
    queryFn: () => apiClient(`/exams?user_id=${user?.id}`),
    enabled: !!user?.id,
  });

  return (
    <div className="p-6 lg:p-8">
      <h1 className="font-display font-bold text-3xl text-slate mb-8">Mock Tests</h1>
      {isLoading && <div className="font-mono text-xs text-ink-faint">Loading tests...</div>}
      {error && <div className="text-red-500 font-sans text-sm">Error loading tests. Please check connection.</div>}
      
      <div className="space-y-3">
        {quizzes && quizzes.length === 0 && (
          <p className="font-sans text-sm text-ink-muted">No mock tests available for your subscription.</p>
        )}
        {quizzes?.map((q: any) => (
          <div key={q.id} className="flex flex-col sm:flex-row sm:items-center justify-between bg-chalk border border-border-soft rounded-sm p-6 hover:border-mint/30 transition-all">
            <div>
              <div className="font-sans text-[15px] font-medium text-ink">{q.title}</div>
              <div className="font-mono text-[11px] text-ink-faint mt-1">{q.total_questions || 0} questions · {Math.round((q.duration_seconds || 0) / 60)} min</div>
              <div className="font-mono text-[10px] text-ink-faint mt-1">
                Attempts: {q.attempts_used ?? 0}/{q.max_attempts ?? 2}
              </div>
            </div>
            <div className="flex items-center gap-4 mt-3 sm:mt-0">
              {q.is_finished ? (
                <>
                  <span className="font-display font-black text-2xl text-mint">Done</span>
                  <Link to={`/dashboard/quiz/${q.id}/result`} className="font-mono text-xs text-mint hover:text-mint-dark">View Result →</Link>
                </>
              ) : q.attempts_used > 0 ? (
                <>
                  <Link to={`/dashboard/quiz/${q.id}/exam`} className="magnetic bg-slate text-chalk rounded-sm px-5 py-2 font-sans text-sm font-semibold hover:bg-slate-light transition-all">
                    {q.has_active_attempt ? 'Resume Exam' : 'Retake'}
                  </Link>
                  <Link to={`/dashboard/quiz/${q.id}/result`} className="font-mono text-xs text-mint hover:text-mint-dark">View History →</Link>
                </>
              ) : (
                <Link to={`/dashboard/quiz/${q.id}/exam`} className="magnetic bg-slate text-chalk rounded-sm px-5 py-2 font-sans text-sm font-semibold hover:bg-slate-light transition-all">
                  Start Exam
                </Link>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
