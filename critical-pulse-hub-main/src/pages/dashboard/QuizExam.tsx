import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { apiClient, refreshStudentSession } from '@/lib/apiClient';
import { isExpiredTokenError } from '@/lib/authToken';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ChevronLeft, ChevronRight, Check, Loader2 } from 'lucide-react';

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
  const [isFinishing, setIsFinishing] = useState(false);
  const examStartedRef = useRef(false);
  const deadlineRef = useRef<number | null>(null);
  const timedOutRef = useRef(false);
  const saveQueueRef = useRef<Promise<void>>(Promise.resolve());
  const failedSaveIdsRef = useRef<Set<number>>(new Set());
  const finishInFlightRef = useRef(false);
  const currentIdxRef = useRef(1);
  const selectedAnswersRef = useRef<string[]>([]);
  const localAnswersRef = useRef<Record<number, string[]>>({});
  const flushAllAnswersRef = useRef<() => Promise<number>>(async () => 0);
  const mergedLocalRef = useRef(false);

  const bundleKey = ['examAllQuestions', id, user?.id] as const;
  const localStoreKey =
    user?.id && id ? `examLocalAnswers:${id}:${user.id}` : null;

  const readLocalStore = useCallback((): Record<number, string[]> => {
    if (!localStoreKey) return {};
    try {
      const raw = localStorage.getItem(localStoreKey);
      if (!raw) return {};
      const parsed = JSON.parse(raw) as Record<string, string[]>;
      const out: Record<number, string[]> = {};
      for (const [k, v] of Object.entries(parsed || {})) {
        const qid = Number(k);
        if (!Number.isFinite(qid) || !Array.isArray(v) || !v.length) continue;
        out[qid] = v.map((a) => String(a).toUpperCase());
      }
      return out;
    } catch {
      return {};
    }
  }, [localStoreKey]);

  const writeLocalStore = useCallback(
    (map: Record<number, string[]>) => {
      if (!localStoreKey) return;
      try {
        const payload: Record<string, string[]> = {};
        for (const [qid, answers] of Object.entries(map)) {
          if (answers?.length) payload[String(qid)] = answers;
        }
        localStorage.setItem(localStoreKey, JSON.stringify(payload));
      } catch {
        // ignore quota / private mode
      }
    },
    [localStoreKey],
  );

  const clearLocalStore = useCallback(() => {
    if (!localStoreKey) return;
    try {
      localStorage.removeItem(localStoreKey);
    } catch {
      // ignore
    }
  }, [localStoreKey]);

  const syncExamDeadline = useCallback((seconds: number, force = false) => {
    if (seconds <= 0) return;
    const nextDeadline = Date.now() + seconds * 1000;
    if (
      force ||
      deadlineRef.current === null ||
      nextDeadline < deadlineRef.current - 2000
    ) {
      deadlineRef.current = nextDeadline;
      setTimeRemaining(seconds);
    }
  }, []);

  const pauseExam = useCallback(() => {
    if (!user?.id || !id) return;
    void apiClient(`/exams/${id}/pause?user_id=${user.id}`, { method: 'POST' }).catch(() => {});
  }, [id, user?.id]);

  const updateLocalAnswer = useCallback(
    (questionId: number, answers: string[]) => {
      const normalized = answers.map((a) => a.toUpperCase());
      if (normalized.length) {
        localAnswersRef.current[questionId] = normalized;
      } else {
        delete localAnswersRef.current[questionId];
      }
      writeLocalStore(localAnswersRef.current);
      queryClient.setQueryData<ExamBundle>(bundleKey, (old) => {
        if (!old) return old;
        return {
          ...old,
          questions: old.questions.map((q) =>
            q.id === questionId ? { ...q, user_answer: normalized.length ? normalized : null } : q,
          ),
        };
      });
    },
    [queryClient, bundleKey, writeLocalStore],
  );

  const shouldPersistAnswer = (answers: string[], prior?: string[] | null) =>
    answers.length > 0 || (prior?.length ?? 0) > 0;

  const flushAllAnswers = useCallback(async () => {
    const bundle = queryClient.getQueryData<ExamBundle>(bundleKey);
    const fromBundle: Record<number, string[]> = {};
    for (const q of bundle?.questions ?? []) {
      if (q.user_answer?.length) {
        fromBundle[q.id] = q.user_answer.map((a) => a.toUpperCase());
      }
    }
    const merged = { ...fromBundle, ...localAnswersRef.current };
    localAnswersRef.current = merged;
    writeLocalStore(merged);

    const answers = Object.entries(merged)
      .filter(([, vals]) => vals.length > 0)
      .map(([questionId, vals]) => ({
        question_id: Number(questionId),
        answers: vals,
      }));

    if (!answers.length) return 0;

    await refreshStudentSession();
    const res = await apiClient(`/exams/${id}/answers/bulk`, {
      method: 'POST',
      body: JSON.stringify({
        user_id: Number(user?.id),
        answers,
      }),
    });
    failedSaveIdsRef.current.clear();
    return Number(res?.saved || answers.length);
  }, [bundleKey, id, queryClient, user?.id, writeLocalStore]);

  const saveAnswer = useCallback(
    (questionId: number, displayId: number, answers: string[], options?: { await?: boolean }) => {
      updateLocalAnswer(questionId, answers);
      const request = saveQueueRef.current
        .catch(() => {})
        .then(async () => {
          const body = JSON.stringify({
            user_id: Number(user?.id),
            question_id: questionId,
            display_question_id: displayId,
            answers,
            is_last_question: false,
          });
          try {
            await apiClient(`/exams/${id}/answer`, { method: 'POST', body });
            failedSaveIdsRef.current.delete(questionId);
          } catch (firstErr) {
            try {
              await apiClient(`/exams/${id}/answer`, { method: 'POST', body });
              failedSaveIdsRef.current.delete(questionId);
            } catch {
              failedSaveIdsRef.current.add(questionId);
              throw firstErr;
            }
          }
        });
      saveQueueRef.current = request.then(
        () => undefined,
        () => undefined,
      );
      if (options?.await) return request;
      void request.catch(() => {});
      return Promise.resolve();
    },
    [id, user?.id, updateLocalAnswer],
  );

  const startExamMutation = useMutation({
    mutationFn: async () => {
      const data = await apiClient(`/exams/${id}/start?user_id=${user?.id}`, { method: 'POST' });
      try {
        const resumed = await apiClient(`/exams/${id}/resume?user_id=${user?.id}`, { method: 'POST' });
        const rem = resumed?.remaining_seconds ?? data.attempt.remaining_seconds;
        return { ...data, attempt: { ...data.attempt, remaining_seconds: rem } };
      } catch {
        return data;
      }
    },
    onSuccess: (data) => {
      setCurrentIdx(data.attempt.current_question_no);
      syncExamDeadline(data.attempt.remaining_seconds, true);
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
  const answeredCount = questions.filter((q) => (q.user_answer?.length ?? 0) > 0).length;

  currentIdxRef.current = currentIdx;
  selectedAnswersRef.current = selectedAnswers;
  flushAllAnswersRef.current = flushAllAnswers;

  // Merge browser-backed answers into the exam bundle (covers failed/offline POSTs).
  useEffect(() => {
    if (!examBundle?.questions?.length || mergedLocalRef.current) return;
    mergedLocalRef.current = true;
    const stored = readLocalStore();
    localAnswersRef.current = { ...stored };
    if (!Object.keys(stored).length) return;
    queryClient.setQueryData<ExamBundle>(bundleKey, (old) => {
      if (!old) return old;
      return {
        ...old,
        questions: old.questions.map((q) => {
          const local = stored[q.id];
          if (!local?.length) return q;
          if ((q.user_answer?.length ?? 0) > 0) return q;
          return { ...q, user_answer: local };
        }),
      };
    });
  }, [examBundle, bundleKey, queryClient, readLocalStore]);

  // Sync timer from bundle only when it has positive time (never reset a running clock to 0).
  useEffect(() => {
    if (examBundle?.remaining_seconds && examBundle.remaining_seconds > 0) {
      syncExamDeadline(examBundle.remaining_seconds);
    }
  }, [examBundle?.remaining_seconds, syncExamDeadline]);

  // Stable countdown driven by a wall-clock deadline.
  useEffect(() => {
    if (!examReady) return;

    const tick = () => {
      if (deadlineRef.current === null) return;
      const left = Math.max(0, Math.floor((deadlineRef.current - Date.now()) / 1000));
      setTimeRemaining(left);
      if (left === 0 && !timedOutRef.current) {
        timedOutRef.current = true;
        if (finishInFlightRef.current) return;
        finishInFlightRef.current = true;
        setIsFinishing(true);
        void (async () => {
          try {
            const bundle = queryClient.getQueryData<ExamBundle>(bundleKey);
            const idx = currentIdxRef.current;
            const selected = selectedAnswersRef.current;
            const q = bundle?.questions?.[idx - 1];
            if (q && shouldPersistAnswer(selected, q.user_answer)) {
              updateLocalAnswer(q.id, selected);
            }
            // Persist all local answers before closing — otherwise results show 0 answered.
            await Promise.race([
              flushAllAnswersRef.current().catch(() => 0),
              new Promise((r) => setTimeout(r, 45000)),
            ]);
            await Promise.race([
              apiClient(`/exams/${id}/finish?user_id=${user?.id}`, { method: 'POST' }),
              new Promise((_, rej) => setTimeout(() => rej(new Error('timeout')), 20000)),
            ]).catch(() => {});
            // Grace re-sync in case finish closed the attempt before bulk completed.
            await Promise.race([
              flushAllAnswersRef.current().catch(() => 0),
              new Promise((r) => setTimeout(r, 20000)),
            ]);
            clearLocalStore();
          } catch {
            // Still land on result — keep local backup if sync may have failed.
          } finally {
            navigate(`/dashboard/quiz/${id}/result`);
          }
        })();
      }
    };

    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [examReady, id, user?.id, navigate, queryClient, bundleKey, updateLocalAnswer, clearLocalStore]);

  // Keep the auth token alive for the full exam duration.
  useEffect(() => {
    if (!examReady) return;
    void refreshStudentSession();
    const intervalId = window.setInterval(() => {
      void refreshStudentSession();
    }, 10 * 60 * 1000);
    return () => window.clearInterval(intervalId);
  }, [examReady]);

  // Pause the attempt when leaving so remaining time is preserved server-side.
  useEffect(() => {
    if (!examReady || !user?.id || !id) return;

    const onLeave = () => pauseExam();
    window.addEventListener('beforeunload', onLeave);
    return () => {
      onLeave();
      window.removeEventListener('beforeunload', onLeave);
    };
  }, [examReady, id, user?.id, pauseExam]);

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
    if (currentQ && shouldPersistAnswer(selectedAnswers, currentQ.user_answer)) {
      saveAnswer(currentQ.id, currentIdx, selectedAnswers);
    }
    setCurrentIdx(nextIdx);
  };

  const finishExamAndNavigate = useCallback(async () => {
    if (isFinishing || finishInFlightRef.current) return;
    finishInFlightRef.current = true;
    setIsFinishing(true);

    const goToResult = (clearLocal = true) => {
      if (clearLocal) clearLocalStore();
      navigate(`/dashboard/quiz/${id}/result`);
    };

    const withTimeout = async <T,>(promise: Promise<T>, ms: number): Promise<T> => {
      let timer: ReturnType<typeof setTimeout> | undefined;
      try {
        return await Promise.race([
          promise,
          new Promise<T>((_, reject) => {
            timer = setTimeout(() => reject(new Error('Request timed out')), ms);
          }),
        ]);
      } finally {
        if (timer) clearTimeout(timer);
      }
    };

    const postFinish = async () => {
      await withTimeout(
        apiClient(`/exams/${id}/finish?user_id=${user?.id}`, { method: 'POST' }),
        20000,
      );
    };

    const localAnswerCount = () =>
      Object.values({
        ...Object.fromEntries(
          (queryClient.getQueryData<ExamBundle>(bundleKey)?.questions ?? [])
            .filter((q) => (q.user_answer?.length ?? 0) > 0)
            .map((q) => [q.id, q.user_answer as string[]]),
        ),
        ...localAnswersRef.current,
      }).filter((v) => Array.isArray(v) && v.length > 0).length;

    try {
      await refreshStudentSession();
      if (currentQ && shouldPersistAnswer(selectedAnswers, currentQ.user_answer)) {
        updateLocalAnswer(currentQ.id, selectedAnswers);
        await withTimeout(
          saveAnswer(currentQ.id, currentIdx, selectedAnswers, { await: true }),
          15000,
        ).catch(() => {});
      }
      await withTimeout(saveQueueRef.current.catch(() => {}), 15000).catch(() => {});

      // Sync every local answer before closing the attempt. If this fails and the
      // student had answers only in the browser, finishing would show 0/answered.
      let bulkSaved = 0;
      try {
        bulkSaved = await withTimeout(flushAllAnswers(), 45000);
      } catch (bulkErr) {
        console.warn('bulk save failed during finish', bulkErr);
        if (localAnswerCount() > 0) {
          // One more attempt after refreshing the session.
          await refreshStudentSession();
          try {
            bulkSaved = await withTimeout(flushAllAnswers(), 45000);
          } catch {
            finishInFlightRef.current = false;
            setIsFinishing(false);
            alert(
              'Your answers could not be uploaded to the server. Please check your internet connection and tap Finish again — do not close this page or your answers may be lost.',
            );
            return;
          }
        }
      }

      try {
        await postFinish();
      } catch (finishErr) {
        const finishMsg = finishErr instanceof Error ? finishErr.message : '';
        if (
          finishMsg.toLowerCase().includes('failed to fetch') ||
          finishMsg.toLowerCase().includes('timed out') ||
          isExpiredTokenError(finishErr)
        ) {
          await refreshStudentSession();
          try {
            // Re-sync answers in case finish raced ahead of an earlier bulk.
            await withTimeout(flushAllAnswers(), 30000).catch(() => 0);
            await postFinish();
          } catch {
            // Keep local backup if we never confirmed a server sync.
            goToResult(bulkSaved > 0 || localAnswerCount() === 0);
            return;
          }
        } else if (
          finishMsg.includes('No active exam attempt') ||
          finishMsg.includes('Exam time is over')
        ) {
          // Attempt may already be closed — still try a grace bulk sync.
          await withTimeout(flushAllAnswers(), 30000).catch(() => 0);
          goToResult(true);
          return;
        } else {
          throw finishErr;
        }
      }
      goToResult(true);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Could not finish exam';
      if (
        msg.includes('No active exam attempt') ||
        msg.includes('Exam time is over') ||
        msg.toLowerCase().includes('failed to fetch') ||
        msg.toLowerCase().includes('timed out')
      ) {
        await withTimeout(flushAllAnswers(), 30000).catch(() => 0);
        goToResult(true);
        return;
      }
      if (isExpiredTokenError(e)) {
        const refreshed = await refreshStudentSession();
        if (refreshed) {
          try {
            await withTimeout(flushAllAnswers(), 30000).catch(() => 0);
            await postFinish();
            goToResult(true);
            return;
          } catch {
            goToResult(false);
            return;
          }
        }
        finishInFlightRef.current = false;
        setIsFinishing(false);
        alert(
          'Your login session expired while submitting the exam. Please log in again and open Results — if the score shows 0, reopen this exam page so unsaved answers can sync.',
        );
        return;
      }
      finishInFlightRef.current = false;
      setIsFinishing(false);
      alert(msg);
    }
  }, [
    isFinishing,
    currentQ,
    selectedAnswers,
    currentIdx,
    updateLocalAnswer,
    saveAnswer,
    flushAllAnswers,
    clearLocalStore,
    id,
    user?.id,
    navigate,
    queryClient,
    bundleKey,
  ]);

  const handleFinish = () => {
    if (isFinishing) return;
    const unanswered = Math.max(0, total - answeredCount);
    const msg =
      unanswered > 0
        ? `You have answered ${answeredCount} of ${total} questions (${unanswered} unanswered).\n\nFinish and submit for scoring?`
        : `You have answered all ${total} questions.\n\nFinish and submit for scoring?`;
    if (!confirm(msg)) return;
    void finishExamAndNavigate();
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

  const finishOverlay = isFinishing ? (
    <div className="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-chalk-warm/95 backdrop-blur-sm">
      <Loader2 className="w-10 h-10 text-mint animate-spin mb-4" aria-hidden />
      <p className="font-display font-bold text-lg text-slate">Calculating your score…</p>
      <p className="font-mono text-[11px] text-ink-faint mt-2 uppercase tracking-widest">
        Please wait
      </p>
    </div>
  ) : null;

  return (
    <div className="flex flex-col min-h-screen bg-chalk-warm">
      {finishOverlay}
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
                        disabled={isFinishing}
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
            <span className="font-mono text-[9px] text-ink-faint">
              {answeredCount}/{total || '--'} answered
            </span>
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
                      disabled={isFinishing}
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
              onClick={handleFinish}
              disabled={isFinishing}
              className="w-full bg-cherry text-white rounded-sm py-4 font-sans font-bold text-xs tracking-widest uppercase hover:bg-cherry-dark transition-all shadow-md active:scale-95 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {isFinishing ? 'Finishing…' : 'Finish Exam'}
            </button>
            <p className="font-mono text-[9px] text-ink-faint text-center">Progress saved automatically</p>
          </div>
        </div>
      </div>

      {/* Bottom bar */}
      <div className="h-[72px] bg-chalk border-t border-border-soft px-6 lg:px-8 flex items-center justify-between sticky bottom-0 z-40">
        <button
          onClick={() => goToQuestion(currentIdx - 1)}
          disabled={currentIdx === 1 || total === 0 || isFinishing}
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
                handleFinish();
              }
            }}
            disabled={total === 0 || isFinishing}
            className="group flex items-center gap-2 bg-slate text-chalk rounded-sm px-10 py-3 font-sans text-sm font-bold hover:bg-slate-light transition-all shadow-lg active:scale-95 cursor-pointer disabled:opacity-50"
          >
            {isFinishing ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" aria-hidden />
                Calculating…
              </>
            ) : total === 0 ? (
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
