import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/apiClient';
import { openAuthenticatedExport, openAuthenticatedPdf } from '@/lib/apiBase';
import { resolveAdminDocumentHref } from '@/lib/legacyUploadBase';
import AdminDocumentPreview from '@/components/admin/AdminDocumentPreview';
import { ArrowLeft } from 'lucide-react';
import { toast } from 'sonner';
import { useMemo, useState } from 'react';

type UserDetailResponse = {
  user: Record<string, unknown>;
  recent_payments: Array<Record<string, unknown>>;
};

type VideoProgressItem = {
  video_id: number;
  title: string;
  folder: string | null;
  batch: string | null;
  video_status: string | null;
  watched_seconds: number;
  watched_minutes: number;
  is_watched: boolean;
  last_position_seconds: number | null;
  updated_at: string | null;
};

type VideoProgressResponse = {
  user_id: number;
  videos_with_progress: number;
  videos_watched: number;
  total_watched_seconds: number;
  hours_spent: number;
  watched_threshold_seconds: number;
  videos: VideoProgressItem[];
};

type ExamAttemptItem = {
  user_exam_id: number;
  exam_id: number;
  exam_title: string;
  attempt_no: number;
  marks: number;
  total_questions: number;
  score_percent: number | null;
  is_finished: boolean;
  start_date: string | null;
  end_date: string | null;
  batch: string | null;
};

type ExamRollupItem = {
  exam_id: number;
  exam_title: string;
  attempts_count: number;
  completed_count: number;
  best_score_percent: number | null;
  latest_score_percent: number | null;
  latest_marks: number | null;
};

type ExamAttemptsResponse = {
  user_id: number;
  exams_attempted: number;
  tests_done: number;
  mock_tests_completed: number;
  in_progress_count: number;
  avg_score_percent: number | null;
  best_score_percent: number | null;
  exams: ExamRollupItem[];
  attempts: ExamAttemptItem[];
};

type UserUsageResponse = {
  user_id: number;
  videos_watched: number;
  videos_with_progress: number;
  hours_spent: number;
  total_watched_seconds: number;
  exams_attempted: number;
  mock_tests_completed: number;
  tests_done: number;
  in_progress_count: number;
  avg_score_percent: number | null;
  best_score_percent: number | null;
  login_count: number;
  last_login_at: string | null;
  last_activity_at: string | null;
  video: VideoProgressResponse;
  exams: ExamAttemptsResponse;
};

function formatWatchDuration(totalSeconds: number): string {
  const secs = Math.max(0, Math.floor(totalSeconds || 0));
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  if (h > 0) return `${h}h ${m}m ${String(s).padStart(2, '0')}s`;
  if (m > 0) return `${m}m ${String(s).padStart(2, '0')}s`;
  return `${s}s`;
}

function formatUpdatedAt(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString();
}

export default function AdminUserDetail() {
  const { id } = useParams();
  const userId = Number(id);
  const qc = useQueryClient();
  const [offlineNote, setOfflineNote] = useState('');
  const [videoFilter, setVideoFilter] = useState<'all' | 'watched'>('all');
  const [examFilter, setExamFilter] = useState<'all' | 'completed'>('all');

  const { data, isLoading, error } = useQuery({
    queryKey: ['adminUser', userId],
    queryFn: () => apiClient(`/admin/users/${userId}`) as Promise<UserDetailResponse>,
    enabled: Number.isFinite(userId) && userId > 0,
  });

  const {
    data: usage,
    isLoading: usageLoading,
    error: usageError,
  } = useQuery({
    queryKey: ['adminUserUsage', userId],
    queryFn: () => apiClient(`/admin/users/${userId}/usage`) as Promise<UserUsageResponse>,
    enabled: Number.isFinite(userId) && userId > 0,
  });

  const videoProgress = usage?.video;
  const examAttempts = usage?.exams;

  const filteredVideos = useMemo(() => {
    const rows = videoProgress?.videos ?? [];
    if (videoFilter === 'watched') return rows.filter((v) => v.is_watched);
    return rows;
  }, [videoProgress?.videos, videoFilter]);

  const filteredAttempts = useMemo(() => {
    const rows = examAttempts?.attempts ?? [];
    if (examFilter === 'completed') return rows.filter((a) => a.is_finished);
    return rows;
  }, [examAttempts?.attempts, examFilter]);

  const u = data?.user;

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ['adminUser', userId] });
    void qc.invalidateQueries({ queryKey: ['adminUserUsage', userId] });
    void qc.invalidateQueries({ queryKey: ['adminUsers'] });
  };

  const approveMut = useMutation({
    mutationFn: (approve: string) =>
      apiClient(`/admin/users/${userId}/approve`, {
        method: 'POST',
        body: JSON.stringify({ approve }),
      }),
    onSuccess: () => {
      toast.success('Approval updated');
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const offlineMut = useMutation({
    mutationFn: () =>
      apiClient(`/admin/users/${userId}/offline-credit`, {
        method: 'POST',
        body: JSON.stringify({ payment_details: offlineNote || undefined }),
      }),
    onSuccess: () => {
      toast.success('Marked as offline credit');
      setOfflineNote('');
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const syncRazorpayMut = useMutation({
    mutationFn: () =>
      apiClient(`/admin/users/${userId}/sync-razorpay-payment`, { method: 'POST', body: '{}' }),
    onSuccess: (res: { message?: string }) => {
      toast.success(res?.message || 'Payment synced from Razorpay');
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const refundMut = useMutation({
    mutationFn: () => apiClient(`/admin/users/${userId}/refund`, { method: 'POST' }),
    onSuccess: () => {
      toast.success('User marked as refund');
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const docMut = useMutation({
    mutationFn: (document_file_status: string) =>
      apiClient(`/admin/users/${userId}/document-status`, {
        method: 'POST',
        body: JSON.stringify({ document_file_status }),
      }),
    onSuccess: (res: { message?: string; smtp_configured?: boolean; email_queued?: boolean }) => {
      const msg = res?.message || 'Document status saved';
      if (res?.smtp_configured === false) toast.warning(msg);
      else toast.success(msg);
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const pwdMailMut = useMutation({
    mutationFn: () =>
      apiClient('/admin/users/mail/password', {
        method: 'POST',
        body: JSON.stringify({ user_id: userId }),
      }),
    onSuccess: () => toast.success('Login email sent to the user’s address'),
    onError: (e: Error) => toast.error(e.message),
  });

  if (!Number.isFinite(userId) || userId <= 0) {
    return (
      <div className="p-6 lg:p-8">
        <p className="text-red-600 text-sm">Invalid user id.</p>
        <Link to="/admin/users" className="text-mint text-sm mt-4 inline-block">
          Back to users
        </Link>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="p-6 lg:p-8 font-mono text-xs text-ink-faint animate-pulse">Loading user…</div>
    );
  }

  if (error || !u) {
    return (
      <div className="p-6 lg:p-8">
        <Link to="/admin/users" className="flex items-center gap-2 font-mono text-xs text-ink-faint hover:text-mint mb-6">
          <ArrowLeft size={14} /> Back
        </Link>
        <p className="text-red-600 text-sm">{error instanceof Error ? error.message : 'User not found'}</p>
      </div>
    );
  }

  const str = (k: string) => (u[k] != null ? String(u[k]) : '—');
  const approved = str('approve') === '1';
  const payLower = (str('payment_status') || '').toLowerCase();
  const canSendLoginMail = payLower === 'credit' && approved && Boolean(u.has_password);
  const doc1Url = resolveAdminDocumentHref(
    u.document_file_url != null ? String(u.document_file_url) : null,
    u.document_file != null ? String(u.document_file) : null,
  );
  const doc2Url = resolveAdminDocumentHref(
    u.document_file_2_url != null ? String(u.document_file_2_url) : null,
    u.document_file_2 != null ? String(u.document_file_2) : null,
  );
  const access = (u.subscription_access || null) as {
    plan_type_label?: string;
    package_name?: string;
    course_start_at?: string;
    course_end_at?: string;
    access_status?: string;
    days_remaining?: number | null;
    duration_months?: number | null;
  } | null;

  const formatCourseDate = (iso?: string) => {
    if (!iso) return '—';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return '—';
    return d.toLocaleString();
  };

  return (
    <div className="p-6 lg:p-8">
      <Link
        to="/admin/users"
        className="flex items-center gap-2 font-mono text-xs text-ink-faint hover:text-mint mb-6"
      >
        <ArrowLeft size={14} /> Back
      </Link>

      <h1 className="font-display font-bold text-3xl text-slate mb-2">{str('name')}</h1>
      <p className="font-mono text-[11px] text-ink-faint mb-6">
        #{userId} · {str('email')}
      </p>

      <section
        id="usage"
        className="mb-8 max-w-5xl bg-chalk border border-border-soft rounded-sm p-6 space-y-4 scroll-mt-4"
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="font-display font-bold text-lg text-slate">Student usage</h2>
            <p className="font-mono text-[10px] text-ink-faint mt-1">
              Consolidated video + mock-test + login activity
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <a
              href="#video-watching"
              className="rounded-sm border border-border-soft px-3 py-2 font-sans text-xs hover:bg-chalk-warm"
            >
              Video details
            </a>
            <a
              href="#mock-tests"
              className="rounded-sm border border-border-soft px-3 py-2 font-sans text-xs hover:bg-chalk-warm"
            >
              Mock test details
            </a>
            <button
              type="button"
              className="rounded-sm border border-border-strong px-3 py-2 font-sans text-xs font-medium hover:bg-chalk-cool"
              onClick={() =>
                void openAuthenticatedExport(
                  `/admin/users/${userId}/usage/export.csv`,
                  `user_${userId}_usage.csv`,
                ).catch((e: Error) => toast.error(e.message))
              }
            >
              Export CSV
            </button>
          </div>
        </div>

        {usageLoading ? (
          <p className="font-mono text-xs text-ink-faint animate-pulse">Loading usage…</p>
        ) : usageError ? (
          <p className="text-sm text-red-600">
            {(usageError as Error).message || 'Failed to load usage'}
          </p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="bg-chalk-warm border border-border-soft rounded-sm p-3">
              <div className="font-mono text-[10px] text-ink-faint uppercase">Videos watched (≥10 min)</div>
              <div className="font-display font-bold text-2xl text-slate mt-1">{usage?.videos_watched ?? 0}</div>
            </div>
            <div className="bg-chalk-warm border border-border-soft rounded-sm p-3">
              <div className="font-mono text-[10px] text-ink-faint uppercase">Total watch hours</div>
              <div className="font-display font-bold text-2xl text-slate mt-1">{usage?.hours_spent ?? 0}</div>
            </div>
            <div className="bg-chalk-warm border border-border-soft rounded-sm p-3">
              <div className="font-mono text-[10px] text-ink-faint uppercase">Videos with progress</div>
              <div className="font-display font-bold text-2xl text-slate mt-1">{usage?.videos_with_progress ?? 0}</div>
            </div>
            <div className="bg-chalk-warm border border-border-soft rounded-sm p-3">
              <div className="font-mono text-[10px] text-ink-faint uppercase">Exams attempted</div>
              <div className="font-display font-bold text-2xl text-slate mt-1">{usage?.exams_attempted ?? 0}</div>
            </div>
            <div className="bg-chalk-warm border border-border-soft rounded-sm p-3">
              <div className="font-mono text-[10px] text-ink-faint uppercase">Mock tests completed</div>
              <div className="font-display font-bold text-2xl text-slate mt-1">{usage?.mock_tests_completed ?? 0}</div>
            </div>
            <div className="bg-chalk-warm border border-border-soft rounded-sm p-3">
              <div className="font-mono text-[10px] text-ink-faint uppercase">Avg score %</div>
              <div className="font-display font-bold text-2xl text-slate mt-1">
                {usage?.avg_score_percent != null ? usage.avg_score_percent : '—'}
              </div>
            </div>
            <div className="bg-chalk-warm border border-border-soft rounded-sm p-3">
              <div className="font-mono text-[10px] text-ink-faint uppercase">Best score %</div>
              <div className="font-display font-bold text-2xl text-slate mt-1">
                {usage?.best_score_percent != null ? usage.best_score_percent : '—'}
              </div>
            </div>
            <div className="bg-chalk-warm border border-border-soft rounded-sm p-3">
              <div className="font-mono text-[10px] text-ink-faint uppercase">Logins</div>
              <div className="font-display font-bold text-2xl text-slate mt-1">{usage?.login_count ?? 0}</div>
              <div className="font-mono text-[10px] text-ink-faint mt-1">
                Last activity: {formatUpdatedAt(usage?.last_activity_at ?? null)}
              </div>
            </div>
          </div>
        )}
      </section>

      <div className="grid gap-6 lg:grid-cols-2 max-w-5xl">
        <section className="bg-chalk border border-border-soft rounded-sm p-6 space-y-3">
          <h2 className="font-display font-bold text-lg text-slate">Profile</h2>
          {[
            ['Registration type', 'registration_type'],
            ['Batch / subscription', 'subscription'],
            ['Contact', 'contact_number'],
            ['Hospital', 'hospital'],
            ['Qualification', 'qualification'],
            ['Speciality', 'speciality'],
            ['Location', 'state'],
            ['City', 'city'],
            ['PIN', 'pin_code'],
            ['Package ID', 'package_id'],
            ['Coupon', 'coupon_code'],
            ['Created', 'created_at'],
          ].map(([label, key]) => (
            <div key={key} className="flex justify-between gap-4 text-sm border-b border-border-soft/60 pb-2 last:border-0">
              <span className="font-mono text-[10px] text-ink-faint uppercase">{label}</span>
              <span className="text-ink text-right break-all">{str(key)}</span>
            </div>
          ))}
        </section>

        <section className="bg-chalk border border-border-soft rounded-sm p-6 space-y-3">
          <h2 className="font-display font-bold text-lg text-slate">Course access</h2>
          {[
            ['Plan type', access?.plan_type_label || '—'],
            ['Package', access?.package_name || '—'],
            ['Duration', access?.duration_months ? `${access.duration_months} months` : '—'],
            ['Course started', formatCourseDate(access?.course_start_at)],
            ['Course ends', formatCourseDate(access?.course_end_at)],
            [
              'Access status',
              access?.access_status
                ? access.access_status.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
                : '—',
            ],
            [
              'Days remaining',
              typeof access?.days_remaining === 'number' ? String(access.days_remaining) : '—',
            ],
          ].map(([label, value]) => (
            <div key={label} className="flex justify-between gap-4 text-sm border-b border-border-soft/60 pb-2 last:border-0">
              <span className="font-mono text-[10px] text-ink-faint uppercase">{label}</span>
              <span className="text-ink text-right break-all">{value}</span>
            </div>
          ))}
        </section>

        <section
          id="video-watching"
          className="bg-chalk border border-border-soft rounded-sm p-6 space-y-4 lg:col-span-2 scroll-mt-4"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="font-display font-bold text-lg text-slate">Video watching</h2>
              <p className="font-mono text-[10px] text-ink-faint mt-1">
                Cumulative play time · watched = ≥10 minutes
              </p>
            </div>
            <button
              type="button"
              className="rounded-sm border border-border-strong px-3 py-2 font-sans text-xs font-medium hover:bg-chalk-cool"
              onClick={() =>
                void openAuthenticatedExport(
                  `/admin/users/${userId}/video-progress/export.csv`,
                  `user_${userId}_video_progress.csv`,
                ).catch((e: Error) => toast.error(e.message))
              }
            >
              Export CSV
            </button>
          </div>

          {usageLoading ? (
            <p className="font-mono text-xs text-ink-faint animate-pulse">Loading video progress…</p>
          ) : usageError ? (
            <p className="text-sm text-red-600">
              {(usageError as Error).message || 'Failed to load video progress'}
            </p>
          ) : (
            <>
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="bg-chalk-warm border border-border-soft rounded-sm p-3">
                  <div className="font-mono text-[10px] text-ink-faint uppercase">Videos watched (≥10 min)</div>
                  <div className="font-display font-bold text-2xl text-slate mt-1">
                    {videoProgress?.videos_watched ?? 0}
                  </div>
                </div>
                <div className="bg-chalk-warm border border-border-soft rounded-sm p-3">
                  <div className="font-mono text-[10px] text-ink-faint uppercase">With any progress</div>
                  <div className="font-display font-bold text-2xl text-slate mt-1">
                    {videoProgress?.videos_with_progress ?? 0}
                  </div>
                </div>
                <div className="bg-chalk-warm border border-border-soft rounded-sm p-3">
                  <div className="font-mono text-[10px] text-ink-faint uppercase">Total learning hours</div>
                  <div className="font-display font-bold text-2xl text-slate mt-1">
                    {videoProgress?.hours_spent ?? 0}
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => setVideoFilter('all')}
                  className={`rounded-sm px-3 py-1.5 font-sans text-xs border ${
                    videoFilter === 'all'
                      ? 'bg-slate text-chalk border-slate'
                      : 'bg-chalk border-border-soft text-ink-secondary hover:bg-chalk-warm'
                  }`}
                >
                  All progress
                </button>
                <button
                  type="button"
                  onClick={() => setVideoFilter('watched')}
                  className={`rounded-sm px-3 py-1.5 font-sans text-xs border ${
                    videoFilter === 'watched'
                      ? 'bg-slate text-chalk border-slate'
                      : 'bg-chalk border-border-soft text-ink-secondary hover:bg-chalk-warm'
                  }`}
                >
                  Watched (≥10 min)
                </button>
              </div>

              <div className="overflow-x-auto border border-border-soft rounded-sm">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-chalk-cool border-b border-border-soft text-left">
                      <th className="px-3 py-2 font-mono text-[10px] uppercase text-ink-faint">Video</th>
                      <th className="px-3 py-2 font-mono text-[10px] uppercase text-ink-faint">Folder</th>
                      <th className="px-3 py-2 font-mono text-[10px] uppercase text-ink-faint">Duration</th>
                      <th className="px-3 py-2 font-mono text-[10px] uppercase text-ink-faint">Status</th>
                      <th className="px-3 py-2 font-mono text-[10px] uppercase text-ink-faint">Last updated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredVideos.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="px-3 py-8 text-center text-ink-muted font-sans text-sm">
                          No video watch progress recorded yet.
                        </td>
                      </tr>
                    ) : (
                      filteredVideos.map((v) => (
                        <tr key={v.video_id} className="border-b border-border-soft last:border-0">
                          <td className="px-3 py-2 text-ink font-medium max-w-[280px]">
                            <div className="truncate" title={v.title}>
                              {v.title}
                            </div>
                          </td>
                          <td className="px-3 py-2 text-ink-muted">{v.folder || '—'}</td>
                          <td className="px-3 py-2 font-mono text-xs text-ink whitespace-nowrap">
                            {formatWatchDuration(v.watched_seconds)}
                            <span className="text-ink-faint ml-1">({v.watched_minutes} min)</span>
                          </td>
                          <td className="px-3 py-2">
                            {v.is_watched ? (
                              <span className="inline-block rounded-sm bg-mint/15 text-slate px-2 py-0.5 text-[11px] font-sans font-semibold">
                                Watched
                              </span>
                            ) : (
                              <span className="inline-block rounded-sm bg-chalk-warm text-ink-muted px-2 py-0.5 text-[11px] font-sans">
                                In progress
                              </span>
                            )}
                          </td>
                          <td className="px-3 py-2 font-mono text-[11px] text-ink-faint whitespace-nowrap">
                            {formatUpdatedAt(v.updated_at)}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>

        <section
          id="mock-tests"
          className="bg-chalk border border-border-soft rounded-sm p-6 space-y-4 lg:col-span-2 scroll-mt-4"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="font-display font-bold text-lg text-slate">Mock tests</h2>
              <p className="font-mono text-[10px] text-ink-faint mt-1">
                All assessments · score % = marks ÷ total questions (finished only)
              </p>
            </div>
            <button
              type="button"
              className="rounded-sm border border-border-strong px-3 py-2 font-sans text-xs font-medium hover:bg-chalk-cool"
              onClick={() =>
                void openAuthenticatedExport(
                  `/admin/users/${userId}/exam-attempts/export.csv`,
                  `user_${userId}_exam_attempts.csv`,
                ).catch((e: Error) => toast.error(e.message))
              }
            >
              Export CSV
            </button>
          </div>

          {usageLoading ? (
            <p className="font-mono text-xs text-ink-faint animate-pulse">Loading mock-test attempts…</p>
          ) : usageError ? (
            <p className="text-sm text-red-600">
              {(usageError as Error).message || 'Failed to load exam attempts'}
            </p>
          ) : (
            <>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <div className="bg-chalk-warm border border-border-soft rounded-sm p-3">
                  <div className="font-mono text-[10px] text-ink-faint uppercase">Exams attempted</div>
                  <div className="font-display font-bold text-2xl text-slate mt-1">
                    {examAttempts?.exams_attempted ?? 0}
                  </div>
                </div>
                <div className="bg-chalk-warm border border-border-soft rounded-sm p-3">
                  <div className="font-mono text-[10px] text-ink-faint uppercase">Completed attempts</div>
                  <div className="font-display font-bold text-2xl text-slate mt-1">
                    {examAttempts?.mock_tests_completed ?? 0}
                  </div>
                </div>
                <div className="bg-chalk-warm border border-border-soft rounded-sm p-3">
                  <div className="font-mono text-[10px] text-ink-faint uppercase">Avg score %</div>
                  <div className="font-display font-bold text-2xl text-slate mt-1">
                    {examAttempts?.avg_score_percent != null ? examAttempts.avg_score_percent : '—'}
                  </div>
                </div>
                <div className="bg-chalk-warm border border-border-soft rounded-sm p-3">
                  <div className="font-mono text-[10px] text-ink-faint uppercase">Best score %</div>
                  <div className="font-display font-bold text-2xl text-slate mt-1">
                    {examAttempts?.best_score_percent != null ? examAttempts.best_score_percent : '—'}
                  </div>
                </div>
              </div>

              <div>
                <h3 className="font-sans text-sm font-semibold text-slate mb-2">By exam</h3>
                <div className="overflow-x-auto border border-border-soft rounded-sm">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-chalk-cool border-b border-border-soft text-left">
                        <th className="px-3 py-2 font-mono text-[10px] uppercase text-ink-faint">Exam</th>
                        <th className="px-3 py-2 font-mono text-[10px] uppercase text-ink-faint">Attempts</th>
                        <th className="px-3 py-2 font-mono text-[10px] uppercase text-ink-faint">Completed</th>
                        <th className="px-3 py-2 font-mono text-[10px] uppercase text-ink-faint">Best %</th>
                        <th className="px-3 py-2 font-mono text-[10px] uppercase text-ink-faint">Latest %</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(examAttempts?.exams ?? []).length === 0 ? (
                        <tr>
                          <td colSpan={5} className="px-3 py-6 text-center text-ink-muted font-sans text-sm">
                            No mock tests attempted yet.
                          </td>
                        </tr>
                      ) : (
                        (examAttempts?.exams ?? []).map((e) => (
                          <tr key={e.exam_id} className="border-b border-border-soft last:border-0">
                            <td className="px-3 py-2 text-ink font-medium max-w-[280px]">
                              <div className="truncate" title={e.exam_title}>
                                {e.exam_title}
                              </div>
                            </td>
                            <td className="px-3 py-2 font-mono text-xs">{e.attempts_count}</td>
                            <td className="px-3 py-2 font-mono text-xs">{e.completed_count}</td>
                            <td className="px-3 py-2 font-mono text-xs">
                              {e.best_score_percent != null ? `${e.best_score_percent}%` : '—'}
                            </td>
                            <td className="px-3 py-2 font-mono text-xs">
                              {e.latest_score_percent != null ? `${e.latest_score_percent}%` : '—'}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => setExamFilter('all')}
                  className={`rounded-sm px-3 py-1.5 font-sans text-xs border ${
                    examFilter === 'all'
                      ? 'bg-slate text-chalk border-slate'
                      : 'bg-chalk border-border-soft text-ink-secondary hover:bg-chalk-warm'
                  }`}
                >
                  All attempts
                </button>
                <button
                  type="button"
                  onClick={() => setExamFilter('completed')}
                  className={`rounded-sm px-3 py-1.5 font-sans text-xs border ${
                    examFilter === 'completed'
                      ? 'bg-slate text-chalk border-slate'
                      : 'bg-chalk border-border-soft text-ink-secondary hover:bg-chalk-warm'
                  }`}
                >
                  Completed only
                </button>
              </div>

              <div>
                <h3 className="font-sans text-sm font-semibold text-slate mb-2">Attempt history</h3>
                <div className="overflow-x-auto border border-border-soft rounded-sm">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-chalk-cool border-b border-border-soft text-left">
                        <th className="px-3 py-2 font-mono text-[10px] uppercase text-ink-faint">Exam</th>
                        <th className="px-3 py-2 font-mono text-[10px] uppercase text-ink-faint">#</th>
                        <th className="px-3 py-2 font-mono text-[10px] uppercase text-ink-faint">Score</th>
                        <th className="px-3 py-2 font-mono text-[10px] uppercase text-ink-faint">Status</th>
                        <th className="px-3 py-2 font-mono text-[10px] uppercase text-ink-faint">Started</th>
                        <th className="px-3 py-2 font-mono text-[10px] uppercase text-ink-faint">PDF</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredAttempts.length === 0 ? (
                        <tr>
                          <td colSpan={6} className="px-3 py-6 text-center text-ink-muted font-sans text-sm">
                            No attempts to show.
                          </td>
                        </tr>
                      ) : (
                        filteredAttempts.map((a) => (
                          <tr key={a.user_exam_id} className="border-b border-border-soft last:border-0">
                            <td className="px-3 py-2 text-ink font-medium max-w-[240px]">
                              <div className="truncate" title={a.exam_title}>
                                {a.exam_title}
                              </div>
                            </td>
                            <td className="px-3 py-2 font-mono text-xs">{a.attempt_no}</td>
                            <td className="px-3 py-2 font-mono text-xs whitespace-nowrap">
                              {a.is_finished ? (
                                <>
                                  {a.marks}/{a.total_questions}
                                  {a.score_percent != null ? (
                                    <span className="text-ink-faint ml-1">({a.score_percent}%)</span>
                                  ) : null}
                                </>
                              ) : (
                                '—'
                              )}
                            </td>
                            <td className="px-3 py-2">
                              {a.is_finished ? (
                                <span className="inline-block rounded-sm bg-mint/15 text-slate px-2 py-0.5 text-[11px] font-sans font-semibold">
                                  Done
                                </span>
                              ) : (
                                <span className="inline-block rounded-sm bg-chalk-warm text-ink-muted px-2 py-0.5 text-[11px] font-sans">
                                  In progress
                                </span>
                              )}
                            </td>
                            <td className="px-3 py-2 font-mono text-[11px] text-ink-faint whitespace-nowrap">
                              {formatUpdatedAt(a.start_date)}
                            </td>
                            <td className="px-3 py-2">
                              {a.is_finished ? (
                                <button
                                  type="button"
                                  className="text-xs text-slate font-sans underline hover:no-underline"
                                  onClick={() =>
                                    void openAuthenticatedPdf(
                                      `/admin/quiz/results/${a.user_exam_id}/download.pdf`,
                                    ).catch((e: Error) => toast.error(e.message))
                                  }
                                >
                                  PDF
                                </button>
                              ) : (
                                '—'
                              )}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </section>

        <section className="bg-chalk border border-border-soft rounded-sm p-6 space-y-4">
          <h2 className="font-display font-bold text-lg text-slate">Payment</h2>
          <div className="text-sm space-y-1">
            <div>
              <span className="font-mono text-[10px] text-ink-faint uppercase">Status</span>
              <div className="font-semibold text-slate">{str('payment_status')}</div>
            </div>
            <div>
              <span className="font-mono text-[10px] text-ink-faint uppercase">Type / date</span>
              <div className="text-ink-muted">
                {str('payment_type')} · {str('payment_date')}
              </div>
            </div>
            <div>
              <span className="font-mono text-[10px] text-ink-faint uppercase">Amount</span>
              <div>
                {str('currency_name')} {str('total_amount')}
              </div>
            </div>
          </div>

          <div className="flex flex-wrap gap-2 pt-2">
            <button
              type="button"
              disabled={approveMut.isPending}
              onClick={() => approveMut.mutate(approved ? '0' : '1')}
              className="rounded-sm border border-border-strong px-3 py-2 font-sans text-xs font-medium hover:bg-chalk-cool"
            >
              {approved ? 'Unapprove' : 'Approve'}
            </button>
            {payLower !== 'credit' && (
              <button
                type="button"
                disabled={syncRazorpayMut.isPending}
                onClick={() => {
                  if (!window.confirm('Fetch captured payment from Razorpay and mark user as Credit?')) return;
                  syncRazorpayMut.mutate();
                }}
                className="rounded-sm bg-mint/15 border border-mint/30 px-3 py-2 font-sans text-xs font-semibold text-slate"
              >
                Sync Razorpay payment
              </button>
            )}
            <button
              type="button"
              disabled={offlineMut.isPending}
              onClick={() => {
                if (!window.confirm('Mark this user as paid offline (Credit + approved)?')) return;
                offlineMut.mutate();
              }}
              className="rounded-sm bg-mint/15 border border-mint/30 px-3 py-2 font-sans text-xs font-semibold text-slate"
            >
              Offline credit
            </button>
            <button
              type="button"
              disabled={refundMut.isPending}
              onClick={() => {
                if (!window.confirm('Mark user payment as Refund and unapprove?')) return;
                refundMut.mutate();
              }}
              className="rounded-sm bg-blush/10 border border-blush/40 px-3 py-2 font-sans text-xs font-semibold text-blush"
            >
              Refund
            </button>
          </div>
          <div>
            <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">Offline payment note</label>
            <input
              value={offlineNote}
              onChange={(e) => setOfflineNote(e.target.value)}
              placeholder="Optional details stored on user"
              className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
            />
          </div>
        </section>

        <section className="bg-chalk border border-border-soft rounded-sm p-6 space-y-4 lg:col-span-2">
          <h2 className="font-display font-bold text-lg text-slate">Documents (registration upload)</h2>
          <p className="text-xs text-ink-muted">
            Review the medical registration certificate uploaded at registration. Approving the document also sets
            account status to <strong>Approved</strong> (same as legacy PHP admin).
          </p>

          <div className="space-y-4">
            <div>
              <p className="font-mono text-[10px] text-ink-faint uppercase mb-2">Primary document</p>
              <p className="text-xs text-ink-muted break-all mb-2">{str('document_file')}</p>
              {doc1Url ? (
                <a
                  href={doc1Url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex text-xs font-semibold text-mint hover:underline mb-3"
                >
                  Open in new tab
                </a>
              ) : null}
              <AdminDocumentPreview
                userId={userId}
                filename={u.document_file != null ? String(u.document_file) : null}
                file={1}
                label="Registration document"
              />
            </div>

            {(u.document_file_2 != null && String(u.document_file_2).trim() !== '') || doc2Url ? (
              <div className="pt-4 border-t border-border-soft">
                <p className="font-mono text-[10px] text-ink-faint uppercase mb-2">Secondary file</p>
                <p className="text-xs text-ink-muted break-all mb-2">{str('document_file_2')}</p>
                {doc2Url ? (
                  <a
                    href={doc2Url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex text-xs font-semibold text-mint hover:underline mb-3"
                  >
                    Open in new tab
                  </a>
                ) : null}
                <AdminDocumentPreview
                  userId={userId}
                  filename={u.document_file_2 != null ? String(u.document_file_2) : null}
                  file={2}
                  label="Secondary document"
                />
              </div>
            ) : null}
          </div>

          <div>
            <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">Document decision</label>
            <select
              value={
                u.document_file_status != null && u.document_file_status !== ''
                  ? String(u.document_file_status)
                  : '0'
              }
              onChange={(e) => {
                const v = e.target.value;
                if (v === '0') return;
                const msg =
                  v === '1'
                    ? 'Approve this document and mark the user account as approved?'
                    : 'Deny this document?';
                if (!window.confirm(msg)) return;
                docMut.mutate(v);
              }}
              disabled={docMut.isPending || !(u.document_file && String(u.document_file).trim())}
              className="bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm w-full max-w-xs"
            >
              <option value="0">Pending review</option>
              <option value="1">Approve document</option>
              <option value="2">Deny document</option>
            </select>
          </div>
        </section>

        <section className="bg-chalk border border-border-soft rounded-sm p-6 space-y-4">
          <h2 className="font-display font-bold text-lg text-slate">Send login email</h2>
          <p className="text-xs text-ink-muted">
            Sends login details to <strong className="text-slate">{str('email')}</strong> (same as PHP admin “Send Mail”): payment must be Credit, account approved, and a legacy-stored password present.
          </p>
          {canSendLoginMail ? (
            <button
              type="button"
              disabled={pwdMailMut.isPending}
              onClick={() => pwdMailMut.mutate()}
              className="magnetic bg-slate text-chalk rounded-sm px-4 py-2 font-sans text-xs font-semibold disabled:opacity-50"
            >
              {pwdMailMut.isPending ? 'Sending…' : 'Send login email'}
            </button>
          ) : (
            <p className="text-xs text-ink-faint">
              Not available: payment must be Credit, account approved, and user must have a password on file.
            </p>
          )}
        </section>
      </div>

      {data.recent_payments?.length ? (
        <section className="mt-10 max-w-5xl">
          <h2 className="font-display font-bold text-xl text-slate mb-4">Recent package payments</h2>
          <div className="overflow-x-auto bg-chalk border border-border-soft rounded-sm">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-chalk-cool border-b border-border-soft">
                  <th className="text-left px-4 py-2 font-mono text-[10px] text-ink-faint uppercase">ID</th>
                  <th className="text-left px-4 py-2 font-mono text-[10px] text-ink-faint uppercase">Type</th>
                  <th className="text-left px-4 py-2 font-mono text-[10px] text-ink-faint uppercase">Batch</th>
                  <th className="text-left px-4 py-2 font-mono text-[10px] text-ink-faint uppercase">Status</th>
                  <th className="text-left px-4 py-2 font-mono text-[10px] text-ink-faint uppercase">Date</th>
                </tr>
              </thead>
              <tbody>
                {data.recent_payments.map((p) => (
                  <tr key={String(p.id)} className="border-b border-border-soft">
                    <td className="px-4 py-2 font-mono text-xs">#{String(p.id)}</td>
                    <td className="px-4 py-2">{String(p.package_type ?? '')}</td>
                    <td className="px-4 py-2">{String(p.subscription ?? '')}</td>
                    <td className="px-4 py-2">{String(p.payment_status ?? '')}</td>
                    <td className="px-4 py-2 font-mono text-xs">{String(p.payment_date ?? '')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </div>
  );
}
