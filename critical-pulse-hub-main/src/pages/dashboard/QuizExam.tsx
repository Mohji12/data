import { useState, useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { apiClient } from '@/lib/apiClient';
import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query';
import { ChevronLeft, ChevronRight, Check } from 'lucide-react';

const letters = ['A', 'B', 'C', 'D', 'E'];

export default function QuizExam() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const queryClient = useQueryClient();
  
  const [currentIdx, setCurrentIdx] = useState(1);
  const [timeRemaining, setTimeRemaining] = useState<number | null>(null);
  const examStartedRef = useRef(false);

  // 1. Initial Start Exam or Resume
  const { data: currentData, isLoading: examLoading, isPlaceholderData, refetch: refreshQuestion } = useQuery({
    queryKey: ['examQuestion', id, currentIdx],
    queryFn: () => apiClient(`/exams/${id}/question?user_id=${user?.id}&display_question_id=${currentIdx}`),
    enabled: !!user?.id && !!id,
    retry: false,
    placeholderData: keepPreviousData,
  });

  // Handle Initial Start - If the above fails or on first mount, we might need to call /start
  const startExamMutation = useMutation({
    mutationFn: () => apiClient(`/exams/${id}/start?user_id=${user?.id}`, { method: 'POST' }),
    onSuccess: (data) => {
        setCurrentIdx(data.attempt.current_question_no);
        setTimeRemaining(data.attempt.remaining_seconds);
    }
  });

  useEffect(() => {
    if (!user?.id || !id || examStartedRef.current) return;
    examStartedRef.current = true;
    startExamMutation.mutate();
  }, [id, user?.id]);

  // Sync timer from API response
  useEffect(() => {
    if (currentData?.attempt?.remaining_seconds !== undefined) {
      setTimeRemaining(currentData.attempt.remaining_seconds);
    }
  }, [currentData]);

  // Local timer decrement
  useEffect(() => {
    if (timeRemaining === null || timeRemaining <= 0) return;
    const interval = setInterval(() => {
      setTimeRemaining(prev => (prev !== null && prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(interval);
  }, [timeRemaining]);

  // Answer Submission
  const submitAnswerMutation = useMutation({
    mutationFn: (answers: string[]) => apiClient(`/exams/${id}/answer`, {
      method: 'POST',
      body: JSON.stringify({
        user_id: user?.id,
        question_id: currentData.question.id,
        display_question_id: currentIdx,
        answers: answers
      })
    }),
    onSuccess: (data) => {
       queryClient.invalidateQueries({ queryKey: ['examQuestion', id] });
       if (data.finish_exam) {
          navigate(`/dashboard/quiz/${id}/result`);
       }
    }
  });

  const handleSelectOption = (key: string) => {
     // For single-choice exams, we just submit immediately or let them click next
     // In this system, we submit and move next when they click Next.
  };

  const handleFinish = async () => {
     if (confirm("Are you sure you want to finish the exam?")) {
        await apiClient(`/exams/${id}/finish?user_id=${user?.id}`, { method: 'POST' });
        navigate(`/dashboard/quiz/${id}/result`);
     }
  };

  const question = currentData?.question;
  const attempt = currentData?.attempt;
  const total = attempt?.total_questions || 0;
  const currentQ = question;

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  };

  return (
    <div className="flex flex-col min-h-screen bg-chalk-warm">
      {/* Top bar */}
      <div className="h-[64px] bg-chalk border-b border-border-soft px-6 lg:px-8 flex items-center justify-between sticky top-0 z-40">
        <div className="flex flex-col">
            <span className="font-mono text-[10px] text-ink-faint uppercase font-bold tracking-widest">Mock Test</span>
            <span className="font-sans font-extrabold text-sm text-slate truncate max-w-[200px]">{attempt?.exam_title || (examLoading ? 'Loading exam...' : 'Assigned Test')}</span>
        </div>
        <div className="flex items-center gap-6">
            <div className="flex flex-col items-center">
                <span className="font-mono text-[9px] text-ink-faint uppercase">Question</span>
                <span className="font-display font-black text-xl text-slate leading-none">{String(currentIdx).padStart(2, '0')} <span className="text-ink-faint text-xs font-normal">/ {total || '--'}</span></span>
            </div>
            <div className="h-8 w-[1px] bg-border-soft hidden sm:block"></div>
            <div className="flex flex-col items-center">
                <span className="font-mono text-[9px] text-ink-faint uppercase">Remaining</span>
                <span className={`font-display font-black text-xl leading-none ${timeRemaining && timeRemaining < 300 ? 'text-cherry animate-pulse' : 'text-slate'}`}>
                    {formatTime(timeRemaining || 0)}
                </span>
            </div>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Question area */}
        <div className={`flex-1 overflow-y-auto py-4 px-6 lg:px-12 scroll-smooth transition-opacity duration-200 ${isPlaceholderData ? 'opacity-50 pointer-events-none' : 'opacity-100'}`}>
          <div className="max-w-[800px] mx-auto pb-8">
            <style dangerouslySetInnerHTML={{ __html: `
              .exam-content p, .exam-content span { font-size: 16px !important; line-height: 1.5 !important; margin-bottom: 8px !important; }
              .exam-content { font-family: inherit !important; }
            `}} />
            {!currentQ ? (
              <div className="flex flex-col gap-4 animate-pulse pt-8">
                <div className="h-4 bg-border-strong w-24 rounded-sm"></div>
                <div className="h-8 bg-border-strong w-full rounded-sm mt-2"></div>
                <div className="h-6 bg-border-strong w-3/4 rounded-sm"></div>
                <div className="space-y-3 mt-8">
                  {[1, 2, 3, 4].map(i => (
                    <div key={i} className="h-14 bg-border-soft w-full rounded-sm"></div>
                  ))}
                </div>
              </div>
            ) : (
              <>
                <div className="inline-flex items-center gap-2 font-mono text-[9px] text-mint bg-mint-pale px-2 py-0.5 rounded-sm mb-4 uppercase font-bold tracking-tighter">
                   Section {currentIdx <= total/2 ? '01' : '02'} · Multiple Choice
                </div>
                
                {currentQ.image_url && (
                    <div className="mb-8 rounded-sm overflow-hidden border border-border-soft bg-white p-2">
                        <img src={currentQ.image_url} alt="Question Context" className="max-w-full h-auto mx-auto" />
                    </div>
                )}

                <h2 
                    className="font-display font-bold text-[17px] text-slate leading-relaxed mb-4 exam-content"
                    dangerouslySetInnerHTML={{ __html: currentQ.text }}
                />
                
                <div className="grid grid-cols-1 gap-2">
                  {currentQ.options.map((opt: any, i: number) => {
                    const isSelected = currentQ.user_answer?.includes(opt.key);
                    return (
                      <button 
                        key={opt.key} 
                        onClick={() => {
                            submitAnswerMutation.mutate([opt.key]);
                        }}
                        disabled={submitAnswerMutation.isPending}
                        className={`group w-full flex items-center gap-4 border rounded-sm p-3 text-left transition-all duration-200 ${
                           isSelected 
                           ? 'border-mint bg-mint/5' 
                           : 'border-border-soft hover:border-mint/30 hover:bg-chalk shadow-sm'
                        }`}>
                        <div className={`font-mono font-bold text-[10px] w-6 h-6 rounded-full border flex items-center justify-center transition-all ${
                            isSelected ? 'bg-mint text-white border-mint' : 'bg-chalk-cool text-ink-faint border-border-strong group-hover:border-mint/50'
                        }`}>
                            {isSelected ? <Check size={11} /> : opt.key}
                        </div>
                        <span 
                            className={`font-sans text-[14px] leading-snug exam-content ${isSelected ? 'text-slate font-semibold' : 'text-ink-secondary'}`}
                            dangerouslySetInnerHTML={{ __html: opt.text }}
                        />
                      </button>
                    );
                  })}
                </div>
              </>
            )}
          </div>
        </div>

        {/* Right palette - desktop */}
        <div className="hidden xl:flex w-[400px] bg-chalk-warm border-l border-border-soft flex-col">
          <div className="flex items-center justify-between px-6 py-5 border-b border-border-soft bg-chalk">
              <span className="font-mono text-[11px] text-slate font-bold tracking-widest uppercase">Palette</span>
              <span className="font-mono text-[9px] text-ink-faint">{total || '--'} Topics</span>
          </div>
          
          <div className="flex-1 overflow-y-auto p-4">
            {total === 0 ? (
              <div className="grid grid-cols-10 gap-1.5 animate-pulse">
                {Array.from({ length: 40 }, (_, i) => (
                  <div key={i} className="w-7 h-7 rounded-sm bg-border-soft"></div>
                ))}
              </div>
            ) : (
              <div className="grid grid-cols-10 gap-1.5">
                {Array.from({ length: total }, (_, i) => {
                  const num = i + 1;
                  const isCurrent = num === currentIdx;
                  // Since we don't know the full state of all answers from one question call, 
                  // in a real app /all-questions would be used for the palette.
                  return (
                    <button 
                      key={i} 
                      onClick={() => setCurrentIdx(num)}
                      className={`w-7 h-7 rounded-sm text-[10px] font-mono font-bold flex items-center justify-center border transition-all ${
                        isCurrent ? 'bg-slate text-chalk border-slate shadow-md scale-105 z-10' : 'bg-chalk border-border-soft text-ink-faint hover:border-mint/50'
                      }`}>
                      {String(num).padStart(2, '0')}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
          
          <div className="p-6 bg-chalk border-t border-border-soft space-y-3">
             <button 
               onClick={handleFinish}
               className="w-full bg-cherry text-white rounded-sm py-4 font-sans font-bold text-xs tracking-widest uppercase hover:bg-cherry-dark transition-all shadow-md active:scale-95"
             >
                Finish Exam
             </button>
             <p className="font-mono text-[9px] text-ink-faint text-center">Progress saved automatically</p>
          </div>
        </div>
      </div>

      {/* Bottom bar */}
      <div className="h-[72px] bg-chalk border-t border-border-soft px-6 lg:px-8 flex items-center justify-between sticky bottom-0 z-40">
        <button 
          onClick={() => setCurrentIdx(Math.max(1, currentIdx - 1))} 
          disabled={currentIdx === 1}
          className="flex items-center gap-2 border border-border-strong text-ink-secondary rounded-sm px-7 py-3 font-sans text-sm font-semibold hover:bg-chalk-cool transition-all disabled:opacity-20 cursor-pointer"
        >
          <ChevronLeft size={16} /> Previous
        </button>
        
        <div className="flex items-center gap-4">
            <button className="hidden sm:flex items-center gap-2 border border-amber/30 text-amber rounded-sm px-6 py-3 font-sans text-sm font-semibold hover:bg-amber/5 transition-all cursor-pointer">
                Mark Review
            </button>
            
            <button 
              onClick={() => {
                  if (currentIdx < total) {
                      setCurrentIdx(prev => prev + 1);
                  } else {
                      handleFinish();
                  }
              }} 
              disabled={total === 0}
              className="group flex items-center gap-2 bg-slate text-chalk rounded-sm px-10 py-3 font-sans text-sm font-bold hover:bg-slate-light transition-all shadow-lg active:scale-95 cursor-pointer disabled:opacity-50"
            >
              {total === 0 ? 'Loading...' : currentIdx === total ? 'Finish Exam' : <>Next Question <ChevronRight size={16} /></>}
            </button>
        </div>
      </div>
    </div>
  );
}
