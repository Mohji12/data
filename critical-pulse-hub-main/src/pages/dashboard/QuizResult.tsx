import { Link, useParams } from 'react-router-dom';
import { useOdometer } from '@/hooks/useOdometer';
import { useQuery } from '@tanstack/react-query';
import { apiClient, apiDownload } from '@/lib/apiClient';
import { useAuthStore } from '@/store/authStore';
import { CheckCircle, XCircle, ChevronDown, ChevronUp, Loader2 } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

export default function QuizResult() {
  const { id } = useParams();
  const { user } = useAuthStore();
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});
  const [selectedAttemptNo, setSelectedAttemptNo] = useState<number | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);

  const { data: attempts } = useQuery({
    queryKey: ['examAttemptHistory', id],
    queryFn: () => apiClient(`/exams/${id}/results?user_id=${user?.id}`),
    enabled: !!user?.id && !!id,
  });

  const { data: result, isLoading } = useQuery({
    queryKey: ['examResult', id, selectedAttemptNo],
    queryFn: () => {
      const attemptQuery = selectedAttemptNo ? `&attempt_no=${selectedAttemptNo}` : '';
      return apiClient(`/exams/${id}/result?user_id=${user?.id}${attemptQuery}`);
    },
    enabled: !!user?.id && !!id,
  });

  const score = useOdometer(result?.total_marks || 0);

  if (isLoading || !result) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-chalk-warm">
        <Loader2 className="w-10 h-10 text-mint animate-spin mb-4" aria-hidden />
        <p className="font-display font-bold text-lg text-slate">Calculating your score…</p>
        <p className="font-mono text-[11px] text-ink-faint mt-2 uppercase tracking-widest">
          Please wait
        </p>
      </div>
    );
  }

  const toggleExpand = (qid: number) => {
    setExpanded(prev => ({ ...prev, [qid]: !prev[qid] }));
  };

  const handleDownloadPdf = async () => {
    if (!user?.id || !id) return;
    setPdfLoading(true);
    try {
      const attemptQuery = selectedAttemptNo ? `&attempt_no=${selectedAttemptNo}` : '';
      const safeTitle = (result.exam_title || 'exam').replace(/[^\w\-]+/g, '_').slice(0, 40);
      const attemptSuffix = selectedAttemptNo ?? result.attempt_no ?? 1;
      await apiDownload(
        `/exams/${id}/result/download.pdf?user_id=${user.id}${attemptQuery}`,
        `exam_review_${id}_attempt${attemptSuffix}_${safeTitle}.pdf`,
      );
      toast.success('Review PDF downloaded');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Could not generate PDF';
      toast.error(message);
    } finally {
      setPdfLoading(false);
    }
  };

  return (
    <div className="p-6 lg:p-8 max-w-[900px] mx-auto">
      <div className="bg-chalk border border-border-soft rounded-sm p-12 text-center shadow-sm mb-8">
        <div className="relative w-48 h-48 mx-auto mb-6">
          <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
            <circle cx="50" cy="50" r="42" fill="none" stroke="#F0F2F6" strokeWidth="6" />
            <circle cx="50" cy="50" r="42" fill="none" stroke="#06D6A0" strokeWidth="6" strokeLinecap="round"
              strokeDasharray={`${(result.total_marks / result.total_questions) * 100 * 2.64} 264`} className="transition-all duration-1000" />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="font-display font-black text-6xl text-mint leading-none">{score}</span>
            <span className="font-mono text-[13px] text-ink-faint">Marks</span>
          </div>
        </div>
        <h2 className="font-display font-bold text-3xl text-slate mb-4">Exam Completed: {result.exam_title}</h2>
        <p className="font-mono text-[11px] text-ink-faint mb-4 uppercase tracking-wider">Attempt {result.attempt_no || 1}</p>
        <div className="inline-flex items-center gap-2 bg-mint-pale border border-mint/30 rounded-sm px-5 py-2 font-mono text-[11px] text-slate">
          ✓ RECORDED SUCCESSFULLY
        </div>
      </div>

      {!!attempts?.length && (
        <div className="bg-white border border-border-soft rounded-sm p-4 mb-8">
          <label className="font-mono text-[10px] text-ink-faint uppercase tracking-wider block mb-2">Attempt History</label>
          <select
            className="w-full sm:w-[320px] bg-white border border-border-soft rounded-sm py-2 px-3 font-sans text-sm"
            value={selectedAttemptNo ?? ''}
            onChange={(e) => setSelectedAttemptNo(e.target.value ? parseInt(e.target.value, 10) : null)}
          >
            <option value="">Latest Attempt</option>
            {attempts.map((attempt: any) => (
              <option key={attempt.user_exam_id} value={attempt.attempt_no}>
                Attempt {attempt.attempt_no} · Score {attempt.marks || 0} · {attempt.is_finished ? 'Done' : 'In Progress'}
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-12">
        {[
            { label: 'Total Questions', value: result.total_questions },
            { label: 'Answered', value: result.total_answered },
            { label: 'Correct', value: result.total_correct },
            { label: 'Incorrect', value: result.total_wrong }
        ].map(s => (
          <div key={s.label} className="bg-white border border-border-soft rounded-sm p-5 text-center shadow-sm">
            <div className="font-display font-bold text-2xl text-slate">{s.value}</div>
            <div className="font-mono text-[10px] text-ink-faint mt-1 uppercase tracking-tighter">{s.label}</div>
          </div>
        ))}
      </div>

      <style dangerouslySetInnerHTML={{ __html: `
        .review-content p, .review-content span { font-size: 15px !important; line-height: 1.5 !important; font-family: inherit !important; color: inherit !important; background: transparent !important; }
        .review-content { font-family: inherit !important; }
      `}} />
      <h3 className="font-display font-bold text-xl text-slate mb-6">Detailed Review</h3>
      <div className="space-y-4">
          {result.reviews?.map((rev: any, idx: number) => {
              const isExpanded = expanded[rev.id];
              return (
                  <div key={rev.id} className={`bg-white border rounded-sm transition-all ${rev.is_correct ? 'border-mint/20' : 'border-cherry/10'}`}>
                      <button 
                        onClick={() => toggleExpand(rev.id)}
                        className="w-full flex items-center justify-between p-4 text-left"
                      >
                         <div className="flex items-center gap-4">
                             <div className={`w-8 h-8 rounded-full flex items-center justify-center font-mono text-xs ${rev.is_correct ? 'bg-mint text-white' : 'bg-cherry text-white'}`}>
                                 {rev.is_correct ? <CheckCircle size={14} /> : <XCircle size={14} />}
                             </div>
                             <div className="flex flex-col">
                                <span className="font-mono text-[10px] text-ink-faint font-bold uppercase">Question {idx + 1}</span>
                                <span 
                                    className="font-sans text-sm text-slate truncate max-w-[600px] block mt-0.5"
                                    dangerouslySetInnerHTML={{ __html: rev.text }}
                                />
                             </div>
                         </div>
                         {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                      </button>
                      
                      {isExpanded && (
                          <div className="p-6 pt-0 border-t border-slate-50">
                              <div 
                                className="font-sans text-[15px] text-slate mb-6 mt-4 review-content"
                                dangerouslySetInnerHTML={{ __html: rev.text }}
                              />
                              <div className="grid grid-cols-1 gap-2">
                                  {rev.options.map((opt: any) => {
                                      const isCorrect = rev.correct_answer?.includes(opt.key);
                                      const isUser = rev.user_answer?.includes(opt.key);
                                      return (
                                          <div key={opt.key} className={`p-4 rounded-sm border flex items-center justify-between ${
                                              isCorrect ? 'bg-mint/5 border-mint/30' : 
                                              (isUser && !isCorrect) ? 'bg-cherry/5 border-cherry/20' : 'bg-chalk border-border-soft'
                                          }`}>
                                              <div className="flex items-center gap-4">
                                                  <span className="font-mono font-bold text-xs">{opt.key}.</span>
                                                  <span 
                                                    className="font-sans text-sm review-content"
                                                    dangerouslySetInnerHTML={{ __html: opt.text }}
                                                  />
                                              </div>
                                              <div className="flex gap-2">
                                                  {isUser && <span className="font-mono text-[9px] bg-slate text-white px-1.5 py-0.5 rounded-sm uppercase">Your Choice</span>}
                                                  {isCorrect && <span className="font-mono text-[9px] bg-mint text-white px-1.5 py-0.5 rounded-sm uppercase">Correct Answer</span>}
                                              </div>
                                          </div>
                                      );
                                  })}
                              </div>
                          </div>
                      )}
                  </div>
              );
          })}
      </div>

      <div className="flex justify-center gap-4 mt-12 mb-24">
        <Link to="/dashboard/quiz" className="bg-slate text-chalk rounded-sm px-8 py-3 font-sans text-sm font-bold shadow-lg hover:bg-slate-light transition-all">
          ← Back to Tests
        </Link>
        <button
          type="button"
          onClick={() => void handleDownloadPdf()}
          disabled={pdfLoading}
          className="border border-border-strong text-ink hover:bg-chalk-cool rounded-sm px-8 py-3 font-sans text-sm font-semibold transition-all disabled:opacity-50"
        >
          {pdfLoading ? 'Generating PDF…' : 'Generate Review PDF'}
        </button>
      </div>
    </div>
  );
}
