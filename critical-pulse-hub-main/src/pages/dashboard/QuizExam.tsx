import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { apiClient } from '@/lib/apiClient';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ChevronLeft, ChevronRight, Check } from 'lucide-react';

type QuestionPayload = {
  id: number;
  text: string;
  image_url?: string | null;
  marking_description?: string | null;
  answer_type: string;
  options: { key: string; text: string }[];
  user_answer?: string[] | null;
};

type ExamBundle = {
  exam_id: number;
  exam_title: string;
  questions: QuestionPayload[];
  remaining_seconds: number;
};

export default function QuizExam() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const queryClient = useQueryClient();

  const [currentIdx, setCurrentIdx] = useState(1);
  const [timeRemaining, setTimeRemaining] = useState<number | null>(null);
  const [examReady, setExamReady] = useState(false);
  const [selectedAnswers, setSelectedAnswers] = useState<string[]>([]);
  const examStartedRef = useRef(false);

  const bundleKey = ['examAllQuestions', id, user?.id] as const;

  const updateLocalAnswer = useCallback(
    (questionId: number, answers: string[]) => {
      queryClient.setQueryData<ExamBundle>(bundleKey, (old) => {
        if (!old) return old;
        return {
          ...old,
          questions: old.questions.map((q) =>
            q.id === questionId ? { ...q, user_answer: answers.length ? answers : null } : q,
          ),
        };
      });
    },
    [queryClient, bundleKey],
  );

  const saveAnswer = useCallback(
    (questionId: number, displayId: number, answers: string[], options?: { await?: boolean }) => {
      updateLocalAnswer(questionId, answers);
      const request = apiClient(`/exams/${id}/answer`, {
        method: 'POST',
        body: JSON.stringify({
          user_id: user?.id,
          question_id: questionId,
          display_question_id: displayId,
          answers,
          is_last_question: false,
        }),
      });
      if (options?.await) return request;
      void request.catch(() => {});
      return Promise.resolve();
    },
    [id, user?.id, updateLocalAnswer],
  );

  const startExamMutation = useMutation({
    mutationFn: () => apiClient(`/exams/${id}/start?user_id=${user?.id}`, { method: 'POST' }),
    onSuccess: (data) => {
      setCurrentIdx(data.attempt.current_question_no);
      setTimeRemaining(data.attempt.remaining_seconds);
      setExamReady(true);
    },
    onError: () => {
      examStartedRef.current = false;
    },
  });

  useEffect(() => {
    if (!user?.id || !id || examStartedRef.current) return;
    examStartedRef.current = true;
    startExamMutation.mutate();
  }, [id, user?.id]);

  const { data: examBundle, isLoading: questionsLoading } = useQuery({
    queryKey: bundleKey,
    queryFn: () => apiClient(`/exams/${id}/all-questions?user_id=${user?.id}`) as Promise<ExamBundle>,
    enabled: !!user?.id && !!id && examReady,
    staleTime: Infinity,
    gcTime: Infinity,
  });

  const questions = examBundle?.questions ?? [];
  const total = questions.length;
  const currentQ = questions[currentIdx - 1] ?? null;

  // Sync timer from bundle when loaded
  useEffect(() => {
    if (examBundle?.remaining_seconds !== undefined) {
      setTimeRemaining(examBundle.remaining_seconds);
    }
  }, [examBundle?.remaining_seconds]);

  // Local timer decrement
  useEffect(() => {
    if (timeRemaining === null || timeRemaining <= 0) return;
    const interval = setInterval(() => {
      setTimeRemaining((prev) => (prev !== null && prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(interval);
  }, [timeRemaining]);

  // Sync selected options when the active question changes
  useEffect(() => {
    const saved = currentQ?.user_answer;
    setSelectedAnswers(Array.isArray(saved) ? saved.map((a) => a.toUpperCase()) : []);
  }, [currentQ?.id, currentIdx]);

  const handleToggleOption = (key: string) => {
    if (!currentQ) return;
    const upper = key.toUpperCase();
    const next =
      currentQ.answer_type === 'R'
        ? [upper]
        : selectedAnswers.includes(upper)
          ? selectedAnswers.filter((a) => a !== upper)
          : [...selectedAnswers, upper];
    setSelectedAnswers(next);
    saveAnswer(currentQ.id, currentIdx, next);
  };

  const goToQuestion = (nextIdx: number) => {
    if (nextIdx === currentIdx || nextIdx < 1 || nextIdx > total) return;
    if (currentQ) {
      saveAnswer(currentQ.id, currentIdx, selectedAnswers);
    }
    setCurrentIdx(nextIdx);
  };

  const handleFinish = async () => {
    if (!confirm('Are you sure you want to finish the exam?')) return;
    try {
      if (currentQ) {
        await saveAnswer(currentQ.id, currentIdx, selectedAnswers, { await: true });
      }
      await apiClient(`/exams/${id}/finish?user_id=${user?.id}`, { method: 'POST' });
      navigate(`/dashboard/quiz/${id}/result`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Could not finish exam';
      // Attempt may already be closed (e.g. timer expired) — still show results.
      if (msg.includes('No active exam attempt') || msg.includes('Exam time is over')) {
        navigate(`/dashboard/quiz/${id}/result`);
        return;
      }
      alert(msg);
    }
  };

  const startError = startExamMutation.error instanceof Error ? startExamMutation.error.message : null;

  if (startError) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-chalk-warm px-6 text-center">
        <p className="font-sans text-slate font-semibold mb-2">Could not start the exam</p>
        <p className="font-sans text-ink-secondary text-sm mb-6">{startError}</p>
        <button
          onClick={() => navigate('/dashboard/quiz')}
          className="bg-slate text-chalk rounded-sm px-6 py-3 font-sans text-sm font-bold"
        >
          Back to Quiz
        </button>
      </div>
    );
  }

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  };

  const showSkeleton = !examReady || questionsLoading || !currentQ;

  return (
    <div className="flex flex-col min-h-screen bg-chalk-warm">
      {/* Top bar */}
      <div className="h-[64px] bg-chalk border-b border-border-soft px-6 lg:px-8 flex items-center justify-between sticky top-0 z-40">
        <div className="flex flex-col">
          <span className="font-mono text-[10px] text-ink-faint uppercase font-bold tracking-widest">Mock Test</span>
          <span className="font-sans font-extrabold text-sm text-slate truncate max-w-[200px]">
            {examBundle?.exam_title || (showSkeleton ? 'Loading exam...' : 'Assigned Test')}
          </span>
        </div>
        <div className="flex items-center gap-6">
          <div className="flex flex-col items-center">
            <span className="font-mono text-[9px] text-ink-faint uppercase">Question</span>
            <span className="font-display font-black text-xl text-slate leading-none">
              {String(currentIdx).padStart(2, '0')}{' '}
              <span className="text-ink-faint text-xs font-normal">/ {total || '--'}</span>
            </span>
          </div>
          <div className="h-8 w-[1px] bg-border-soft hidden sm:block" />
          <div className="flex flex-col items-center">
            <span className="font-mono text-[9px] text-ink-faint uppercase">Remaining</span>
            <span
              className={`font-display font-black text-xl leading-none ${timeRemaining && timeRemaining < 300 ? 'text-cherry animate-pulse' : 'text-slate'}`}
            >
              {formatTime(timeRemaining || 0)}
            </span>
          </div>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Question area */}
        <div className="flex-1 overflow-y-auto py-4 px-6 lg:px-12 scroll-smooth">
          <div className="max-w-[800px] mx-auto pb-8">
            <style
              dangerouslySetInnerHTML={{
                __html: `
              .exam-content p, .exam-content span { font-size: 16px !important; line-height: 1.5 !important; margin-bottom: 8px !important; }
              .exam-content { font-family: inherit !important; }
            `,
              }}
            />
            {showSkeleton ? (
              <div className="flex flex-col gap-4 animate-pulse pt-8">
                <div className="h-4 bg-border-strong w-24 rounded-sm" />
                <div className="h-8 bg-border-strong w-full rounded-sm mt-2" />
                <div className="h-6 bg-border-strong w-3/4 rounded-sm" />
                <div className="space-y-3 mt-8">
                  {[1, 2, 3, 4].map((i) => (
                    <div key={i} className="h-14 bg-border-soft w-full rounded-sm" />
                  ))}
                </div>
              </div>
            ) : (
              <>
                <div className="inline-flex items-center gap-2 font-mono text-[9px] text-mint bg-mint-pale px-2 py-0.5 rounded-sm mb-4 uppercase font-bold tracking-tighter">
                  Section {currentIdx <= total / 2 ? '01' : '02'} ·{' '}
                  {currentQ.answer_type === 'R' ? 'Single Choice' : 'Multiple Choice'}
                </div>

                {currentQ.answer_type !== 'R' && (
                  <p className="font-sans text-xs text-ink-faint mb-3">Select all options that apply.</p>
                )}

                {currentQ.marking_description && (
                  <p className="font-sans text-sm text-cherry mb-3">({currentQ.marking_description})</p>
                )}

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
                  {currentQ.options.map((opt) => {
                    const optKey = opt.key.toUpperCase();
                    const isSelected = selectedAnswers.includes(optKey);
                    const isMulti = currentQ.answer_type !== 'R';
                    return (
                      <button
                        key={opt.key}
                        onClick={() => handleToggleOption(opt.key)}
                        className={`group w-full flex items-center gap-4 border rounded-sm p-3 text-left transition-colors duration-100 ${
                          isSelected
                            ? 'border-mint bg-mint/5'
                            : 'border-border-soft hover:border-mint/30 hover:bg-chalk shadow-sm'
                        }`}
                      >
                        <div
                          className={`font-mono font-bold text-[10px] w-6 h-6 border flex items-center justify-center transition-colors duration-100 ${
                            isMulti ? 'rounded-sm' : 'rounded-full'
                          } ${
                            isSelected
                              ? 'bg-mint text-white border-mint'
                              : 'bg-chalk-cool text-ink-faint border-border-strong group-hover:border-mint/50'
                          }`}
                        >
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
                  <div key={i} className="w-7 h-7 rounded-sm bg-border-soft" />
                ))}
              </div>
            ) : (
              <div className="grid grid-cols-10 gap-1.5">
                {questions.map((q, i) => {
                  const num = i + 1;
                  const isCurrent = num === currentIdx;
                  const isAnswered = (q.user_answer?.length ?? 0) > 0;
                  return (
                    <button
                      key={q.id}
                      onClick={() => goToQuestion(num)}
                      className={`w-7 h-7 rounded-sm text-[10px] font-mono font-bold flex items-center justify-center border transition-colors duration-100 ${
                        isCurrent
                          ? 'bg-slate text-chalk border-slate shadow-md scale-105 z-10'
                          : isAnswered
                            ? 'bg-mint/10 border-mint/40 text-mint'
                            : 'bg-chalk border-border-soft text-ink-faint hover:border-mint/50'
                      }`}
                    >
                      {String(num).padStart(2, '0')}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <div className="p-6 bg-chalk border-t border-border-soft space-y-3">
            <button
              onClick={() => void handleFinish()}
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
          onClick={() => goToQuestion(currentIdx - 1)}
          disabled={currentIdx === 1 || total === 0}
          className="flex items-center gap-2 border border-border-strong text-ink-secondary rounded-sm px-7 py-3 font-sans text-sm font-semibold hover:bg-chalk-cool transition-all disabled:opacity-20 cursor-pointer"
        >
          <ChevronLeft size={16} /> Previous
        </button>

        <div className="flex items-center gap-4">
          <button
            onClick={() => {
              if (currentIdx < total) {
                goToQuestion(currentIdx + 1);
              } else {
                void handleFinish();
              }
            }}
            disabled={total === 0}
            className="group flex items-center gap-2 bg-slate text-chalk rounded-sm px-10 py-3 font-sans text-sm font-bold hover:bg-slate-light transition-all shadow-lg active:scale-95 cursor-pointer disabled:opacity-50"
          >
            {total === 0 ? (
              'Loading...'
            ) : currentIdx === total ? (
              'Finish Exam'
            ) : (
              <>
                Next Question <ChevronRight size={16} />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
