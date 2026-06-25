import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/apiClient';
import { openAuthenticatedExport } from '@/lib/apiBase';
import { Link } from 'react-router-dom';
import { useState, useMemo, useEffect } from 'react';
import { ChevronLeft, ChevronRight, Search, Download } from 'lucide-react';
import { toast } from 'sonner';
import { resolveAdminDocumentHref } from '@/lib/legacyUploadBase';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';

type BatchRow = { id: number; name: string; status: string };
type EmailTemplateType = 'registration_thank_you' | 'document_verified' | 'document_denied';
type EmailTemplateRow = {
  id: number;
  batch_id: number;
  batch_name?: string | null;
  template_type: EmailTemplateType;
  subject: string;
  body_html: string;
  status: string;
};

type SubscriptionAccess = {
  plan_type?: string | null;
  plan_type_label?: string | null;
  package_name?: string | null;
  duration_months?: number | null;
  course_start_at?: string | null;
  course_end_at?: string | null;
  access_status?: string | null;
  days_remaining?: number | null;
};

type AdminUserRow = {
  id: number;
  registration_type?: string | null;
  subscription?: string | null;
  title?: string | null;
  name?: string | null;
  email?: string | null;
  contact_number?: string | null;
  hospital?: string | null;
  qualification?: string | null;
  speciality?: string | null;
  country_name?: string | null;
  state?: string | null;
  city?: string | null;
  pin_code?: string | null;
  document_file?: string | null;
  document_file_2?: string | null;
  document_file_status?: string | null;
  document_file_url?: string | null;
  document_file_2_url?: string | null;
  currency_name?: string | null;
  total_amount?: number | null;
  payment_status?: string | null;
  payment_type?: string | null;
  payment_id?: string | null;
  approve?: string | null;
  has_password?: boolean;
  encrypted_password?: string | null;
  password_hash?: string | null;
  password_encrypted?: string | null;
  plaintext_password?: string | null;
  created_at?: string | null;
  subscription_access?: SubscriptionAccess | null;
  mock_test_attempts?: {
    default_max_attempts: number;
    batch_override: number | null;
    user_override: number | null;
    effective_max_attempts: number;
  } | null;
};

function resolveDocUrl(u: AdminUserRow, which: 1 | 2): string | null {
  const url = which === 1 ? u.document_file_url : u.document_file_2_url;
  const fn = which === 1 ? u.document_file : u.document_file_2;
  return resolveAdminDocumentHref(url ?? null, fn ?? null);
}

function formatLegacyDateTime(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(d.getDate())}-${pad(d.getMonth() + 1)}-${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function displayName(u: AdminUserRow): string {
  const t = (u.title || '').trim();
  const n = (u.name || '').trim();
  return [t, n].filter(Boolean).join(' ') || '—';
}

function encryptedPasswordValue(rawUser: AdminUserRow | Record<string, unknown>): string | null {
  const u = rawUser as AdminUserRow;
  const raw = rawUser as Record<string, unknown>;
  const candidates = [
    u.plaintext_password,
    typeof raw.plaintext_password === 'string' ? raw.plaintext_password : null,
    u.encrypted_password,
    u.password_hash,
    u.password_encrypted,
    typeof raw.password === 'string' ? raw.password : null,
    typeof raw.password_md5 === 'string' ? raw.password_md5 : null,
    typeof raw.pass_hash === 'string' ? raw.pass_hash : null,
  ];

  for (const candidate of candidates) {
    if (typeof candidate === 'string' && candidate.trim()) return candidate.trim();
  }
  return null;
}

function paymentBadgeClasses(status: string): string {
  const s = status.toLowerCase();
  if (s === 'credit') return 'bg-mint-pale border-mint/25 text-mint';
  if (s === 'failed') return 'bg-blush/15 border-blush/35 text-blush';
  if (s === 'refund') return 'bg-amber-50 border-amber-200 text-amber-800';
  return 'bg-sky-50 border-sky-200 text-sky-800';
}

function paymentBadgeLabel(status?: string | null): string {
  if (!status) return 'Pending';
  const s = status.toLowerCase();
  if (s === 'credit') return 'Success';
  if (s === 'failed') return 'Failed';
  if (s === 'refund') return 'Refund';
  return status;
}

function accessStatusLabel(status?: string | null): string {
  const s = (status || '').toLowerCase();
  if (s === 'active') return 'Active';
  if (s === 'expired') return 'Expired';
  if (s === 'pending') return 'Pending';
  if (s === 'no_payment') return 'Unpaid';
  return status || '—';
}

function accessStatusClasses(status?: string | null): string {
  const s = (status || '').toLowerCase();
  if (s === 'active') return 'bg-mint-pale border-mint/25 text-mint';
  if (s === 'expired') return 'bg-blush/15 border-blush/35 text-blush';
  if (s === 'no_payment') return 'bg-chalk-cool border-border-soft text-ink-faint';
  return 'bg-amber-50 border-amber-200 text-amber-800';
}

function formatCourseDate(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(d.getDate())}-${pad(d.getMonth() + 1)}-${d.getFullYear()}`;
}

export default function AdminUsers() {
  const qc = useQueryClient();
  const [q, setQ] = useState('');
  const [subscription, setSubscription] = useState('');
  const [paymentStatus, setPaymentStatus] = useState('');
  const [approve, setApprove] = useState('');
  const [documentStatus, setDocumentStatus] = useState('');
  const [pendingDocumentsOnly, setPendingDocumentsOnly] = useState(false);
  const [offset, setOffset] = useState(0);
  const [sortBy, setSortBy] = useState<string>('id');
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');
  const limit = 20;

  const [paynowSub, setPaynowSub] = useState('');
  const [paynowLimit, setPaynowLimit] = useState('100');
  const [customSub, setCustomSub] = useState('');
  const [customLimit, setCustomLimit] = useState('100');
  const [customSubject, setCustomSubject] = useState('');
  const [customBody, setCustomBody] = useState('');
  const [tplBatchId, setTplBatchId] = useState<string>('');
  const [tplType, setTplType] = useState<EmailTemplateType>('registration_thank_you');
  const [tplStatus, setTplStatus] = useState<'0' | '1'>('1');
  const [tplId, setTplId] = useState<number | null>(null);
  const [tplSubject, setTplSubject] = useState('');
  const [tplBody, setTplBody] = useState('');
  const [encryptedPasswordById, setEncryptedPasswordById] = useState<Record<number, string>>({});
  const [attemptsUser, setAttemptsUser] = useState<AdminUserRow | null>(null);
  const [attemptsInput, setAttemptsInput] = useState('');

  const queryString = useMemo(() => {
    const p = new URLSearchParams();
    if (q.trim()) p.set('q', q.trim());
    if (subscription.trim()) p.set('subscription', subscription.trim());
    if (paymentStatus.trim()) p.set('payment_status', paymentStatus.trim());
    if (approve !== '') p.set('approve', approve);
    if (documentStatus !== '') p.set('document_status', documentStatus);
    if (pendingDocumentsOnly) p.set('pending_documents_only', 'true');
    p.set('sort_by', sortBy);
    p.set('order', order);
    p.set('offset', String(offset));
    p.set('limit', String(limit));
    return p.toString();
  }, [q, subscription, paymentStatus, approve, documentStatus, pendingDocumentsOnly, sortBy, order, offset]);

  const invalidateUsers = () => {
    void qc.invalidateQueries({ queryKey: ['adminUsers'] });
  };

  const { data: batches } = useQuery({
    queryKey: ['adminMiscBatches'],
    queryFn: () => apiClient('/admin/misc/batches') as Promise<BatchRow[]>,
  });

  const { data, isLoading, error } = useQuery({
    queryKey: ['adminUsers', queryString],
    queryFn: () => apiClient(`/admin/users?${queryString}`),
  });

  const users = useMemo(() => ((data?.items || []) as AdminUserRow[]), [data?.items]);
  const total = useMemo(() => data?.total || 0, [data?.total]);

  const activeBatches = (batches || []).filter((b) => String(b.status ?? '1') === '1');
  const selectedTemplateBatchId = Number(tplBatchId) || 0;

  useEffect(() => {
    if (!activeBatches.length) return;
    if (!tplBatchId) setTplBatchId(String(activeBatches[0].id));
  }, [activeBatches, tplBatchId]);

  const { data: emailTemplates, refetch: refetchTemplate } = useQuery({
    queryKey: ['adminEmailTemplates', selectedTemplateBatchId, tplType],
    enabled: selectedTemplateBatchId > 0,
    queryFn: () =>
      apiClient(
        `/admin/misc/email-templates?batch_id=${selectedTemplateBatchId}&template_type=${encodeURIComponent(tplType)}`,
      ) as Promise<EmailTemplateRow[]>,
  });

  useEffect(() => {
    const rows = emailTemplates || [];
    if (!rows.length) {
      setTplId(null);
      setTplSubject('');
      setTplBody('');
      setTplStatus('1');
      return;
    }
    const row = rows[0];
    setTplId(row.id);
    setTplSubject(row.subject || '');
    setTplBody(row.body_html || '');
    setTplStatus(String(row.status || '1') === '0' ? '0' : '1');
  }, [emailTemplates]);

  useEffect(() => {
    let cancelled = false;

    const usersNeedingDetailLookup = users
      .filter((u) => encryptedPasswordValue(u) == null && !encryptedPasswordById[u.id])
      .map((u) => u.id)
      .filter((id) => Number.isFinite(id) && id > 0);

    if (!usersNeedingDetailLookup.length) return;

    void (async () => {
      const entries = await Promise.all(
        usersNeedingDetailLookup.map(async (userId) => {
          try {
            const detail = await apiClient(`/admin/users/${userId}`) as { user?: Record<string, unknown> };
            const encrypted = detail?.user ? encryptedPasswordValue(detail.user) : null;
            return encrypted ? ([userId, encrypted] as const) : null;
          } catch {
            return null;
          }
        }),
      );

      if (cancelled) return;
      const resolved = entries.filter((entry): entry is readonly [number, string] => entry != null);
      if (!resolved.length) return;

      setEncryptedPasswordById((prev) => {
        const next = { ...prev };
        for (const [userId, value] of resolved) next[userId] = value;
        return next;
      });
    })();

    return () => {
      cancelled = true;
    };
  }, [users, encryptedPasswordById]);

  const exportQuery = useMemo(() => {
    const p = new URLSearchParams();
    if (subscription.trim()) p.set('subscription', subscription.trim());
    if (paymentStatus.trim()) p.set('payment_status', paymentStatus.trim());
    if (approve !== '') p.set('approve', approve);
    const s = p.toString();
    return s ? `?${s}` : '';
  }, [subscription, paymentStatus, approve]);

  const paynowMut = useMutation({
    mutationFn: () =>
      apiClient('/admin/users/mail/paynow', {
        method: 'POST',
        body: JSON.stringify({
          subscription: paynowSub.trim() || null,
          limit: Math.min(500, Math.max(1, Number(paynowLimit) || 100)),
        }),
      }),
    onSuccess: (res: { sent?: number }) => toast.success(`Pay-now emails sent: ${res?.sent ?? 0}`),
    onError: (e: Error) => toast.error(e.message),
  });

  const customMut = useMutation({
    mutationFn: () =>
      apiClient('/admin/users/mail/custom', {
        method: 'POST',
        body: JSON.stringify({
          subject: customSubject.trim(),
          body_html: customBody,
          subscription: customSub.trim() || null,
          limit: Math.min(500, Math.max(1, Number(customLimit) || 100)),
        }),
      }),
    onSuccess: (res: { sent?: number }) => toast.success(`Custom emails sent: ${res?.sent ?? 0}`),
    onError: (e: Error) => toast.error(e.message),
  });

  const saveTemplateMut = useMutation({
    mutationFn: async () => {
      if (!selectedTemplateBatchId) throw new Error('Select a batch first');
      const payload = {
        batch_id: selectedTemplateBatchId,
        template_type: tplType,
        subject: tplSubject.trim(),
        body_html: tplBody.trim(),
        status: tplStatus,
      };
      if (tplId) {
        return apiClient(`/admin/misc/email-templates/${tplId}`, {
          method: 'PUT',
          body: JSON.stringify(payload),
        });
      }
      return apiClient('/admin/misc/email-templates', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    },
    onSuccess: async () => {
      toast.success(tplId ? 'Template updated' : 'Template created');
      await refetchTemplate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const deleteTemplateMut = useMutation({
    mutationFn: (id: number) => apiClient(`/admin/misc/email-templates/${id}`, { method: 'DELETE' }),
    onSuccess: async () => {
      toast.success('Template deleted');
      await refetchTemplate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const docMut = useMutation({
    mutationFn: ({ userId, document_file_status }: { userId: number; document_file_status: string }) =>
      apiClient(`/admin/users/${userId}/document-status`, {
        method: 'POST',
        body: JSON.stringify({ document_file_status }),
      }),
    onSuccess: (res: { message?: string; smtp_configured?: boolean; email_queued?: boolean }) => {
      const msg = res?.message || 'Document status updated';
      if (res?.smtp_configured === false) toast.warning(msg);
      else if (res?.email_queued) toast.success(msg);
      else toast.success(msg);
      invalidateUsers();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const approveMut = useMutation({
    mutationFn: ({ userId, approve: ap }: { userId: number; approve: string }) =>
      apiClient(`/admin/users/${userId}/approve`, {
        method: 'POST',
        body: JSON.stringify({ approve: ap }),
      }),
    onSuccess: () => {
      toast.success('Account status updated');
      invalidateUsers();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const refundMut = useMutation({
    mutationFn: (userId: number) => apiClient(`/admin/users/${userId}/refund`, { method: 'POST' }),
    onSuccess: () => {
      toast.success('Marked as refund');
      invalidateUsers();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const offlineCreditMut = useMutation({
    mutationFn: (userId: number) =>
      apiClient(`/admin/users/${userId}/offline-credit`, {
        method: 'POST',
        body: JSON.stringify({ payment_details: 'Marked paid from admin users list' }),
      }),
    onSuccess: () => {
      toast.success('Payment marked as Credit');
      invalidateUsers();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const syncRazorpayMut = useMutation({
    mutationFn: (userId: number) =>
      apiClient(`/admin/users/${userId}/sync-razorpay-payment`, { method: 'POST', body: '{}' }),
    onSuccess: (res: { message?: string }) => {
      toast.success(res?.message || 'Payment synced from Razorpay');
      invalidateUsers();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const pwdMailMut = useMutation({
    mutationFn: (userId: number) =>
      apiClient('/admin/users/mail/password', {
        method: 'POST',
        body: JSON.stringify({ user_id: userId }),
      }),
    onSuccess: () => toast.success('Login email sent to the user’s address'),
    onError: (e: Error) => toast.error(e.message),
  });

  const mockAttemptsMut = useMutation({
    mutationFn: ({ userId, max_attempts }: { userId: number; max_attempts: number | null }) =>
      apiClient(`/admin/users/${userId}/mock-test-attempts`, {
        method: 'PUT',
        body: JSON.stringify({ max_attempts }),
      }),
    onSuccess: () => {
      toast.success('Mock test attempts updated');
      setAttemptsUser(null);
      invalidateUsers();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const openAttemptsDialog = (user: AdminUserRow) => {
    const info = user.mock_test_attempts;
    setAttemptsUser(user);
    setAttemptsInput(
      info?.user_override != null ? String(info.user_override) : String(info?.effective_max_attempts ?? 2),
    );
  };

  const saveUserAttempts = () => {
    if (!attemptsUser) return;
    const trimmed = attemptsInput.trim();
    if (!trimmed) {
      mockAttemptsMut.mutate({ userId: attemptsUser.id, max_attempts: null });
      return;
    }
    const n = parseInt(trimmed, 10);
    if (Number.isNaN(n) || n < 1 || n > 50) {
      toast.error('Enter a number between 1 and 50, or leave blank to clear override');
      return;
    }
    mockAttemptsMut.mutate({ userId: attemptsUser.id, max_attempts: n });
  };

  const resetPaging = () => setOffset(0);

  const toggleSort = (field: string) => {
    if (sortBy === field) {
      setOrder(order === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setOrder('desc');
    }
    resetPaging();
  };

  const SortIcon = ({ field }: { field: string }) => {
    if (sortBy !== field) return <span className="opacity-20 ml-1">↕</span>;
    return <span className="ml-1 text-mint">{order === 'asc' ? '↑' : '↓'}</span>;
  };

  const COL_COUNT = 27;

  return (
    <div className="p-6 lg:p-8 min-w-0 max-w-full">
      <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-6 mb-8">
        <h1 className="font-display font-bold text-3xl text-slate text-center sm:text-left">Users</h1>
        <button
          type="button"
          onClick={() =>
            void openAuthenticatedExport(`/admin/users/export.csv${exportQuery}`).catch((e) =>
              toast.error(e instanceof Error ? e.message : 'Export failed'),
            )
          }
          className="inline-flex items-center justify-center gap-2 magnetic bg-slate text-chalk rounded-sm px-5 py-2.5 font-sans text-xs font-semibold hover:bg-slate-light shrink-0"
        >
          <Download size={14} />
          Export CSV
        </button>
      </div>

      <div className="mb-6 flex flex-col gap-4 bg-chalk border border-border-soft rounded-sm p-4">
        <div className="relative w-full max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" size={16} />
          <input
            type="text"
            placeholder="Search name, email, phone…"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              resetPaging();
            }}
            className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 pl-9 pr-4 font-sans text-sm outline-none focus:border-mint/50"
          />
        </div>
        <div className="flex flex-wrap gap-4 items-end">
          <div>
            <label className="font-mono text-xs text-ink-faint uppercase block mb-1">Batch</label>
            <select
              value={subscription}
              onChange={(e) => {
                setSubscription(e.target.value);
                resetPaging();
              }}
              className="bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm min-w-[200px]"
            >
              <option value="">All batches</option>
              {activeBatches.map((b) => (
                <option key={b.id} value={b.name}>
                  {b.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="font-mono text-xs text-ink-faint uppercase block mb-1">Document review</label>
            <select
              value={documentStatus}
              onChange={(e) => {
                setDocumentStatus(e.target.value);
                resetPaging();
              }}
              className="bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm min-w-[180px]"
            >
              <option value="">Any document status</option>
              <option value="0">Pending review</option>
              <option value="1">Document approved</option>
              <option value="2">Document denied</option>
            </select>
          </div>
          <div className="flex items-center gap-2 pb-2">
            <input
              id="pending-docs-only"
              type="checkbox"
              checked={pendingDocumentsOnly}
              onChange={(e) => {
                setPendingDocumentsOnly(e.target.checked);
                resetPaging();
              }}
              className="rounded border-border-soft"
            />
            <label htmlFor="pending-docs-only" className="font-sans text-xs text-ink-muted cursor-pointer">
              Only users with document awaiting approval
            </label>
          </div>
          <div>
            <label className="font-mono text-xs text-ink-faint uppercase block mb-1">Payment status</label>
            <select
              value={paymentStatus}
              onChange={(e) => {
                setPaymentStatus(e.target.value);
                resetPaging();
              }}
              className="bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm min-w-[160px]"
            >
              <option value="">Any</option>
              <option value="credit">Credit</option>
              <option value="pending">Pending</option>
              <option value="failed">Failed</option>
              <option value="refund">Refund</option>
            </select>
          </div>
          <div>
            <label className="font-mono text-xs text-ink-faint uppercase block mb-1">Approved</label>
            <select
              value={approve}
              onChange={(e) => {
                setApprove(e.target.value);
                resetPaging();
              }}
              className="bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm min-w-[140px]"
            >
              <option value="">Any</option>
              <option value="1">Yes</option>
              <option value="0">No</option>
            </select>
          </div>
        </div>
      </div>

      <section id="communications" className="mb-8 bg-chalk border border-border-soft rounded-sm p-6 space-y-6">
        <h2 className="font-display font-bold text-lg text-slate">Communications</h2>
        <p className="text-xs text-ink-muted max-w-2xl">
          Pay-now: emails users whose payment is not Credit (same idea as PHP admin). Custom: HTML body sent to Credit users, optionally filtered by batch.
        </p>
        <div className="grid gap-6 md:grid-cols-3">
          <div className="space-y-3 border border-border-soft rounded-sm p-4">
            <h3 className="font-sans text-sm font-semibold text-slate">Pay-now reminder</h3>
            <select
              value={paynowSub}
              onChange={(e) => setPaynowSub(e.target.value)}
              className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
            >
              <option value="">All batches</option>
              {activeBatches.map((b) => (
                <option key={b.id} value={b.name}>
                  {b.name}
                </option>
              ))}
            </select>
            <input
              type="number"
              min={1}
              max={500}
              value={paynowLimit}
              onChange={(e) => setPaynowLimit(e.target.value)}
              className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
              placeholder="Max recipients"
            />
            <button
              type="button"
              disabled={paynowMut.isPending}
              onClick={() => {
                if (!window.confirm('Send pay-now emails to non–credit users for this filter?')) return;
                paynowMut.mutate();
              }}
              className="magnetic bg-slate text-chalk rounded-sm px-4 py-2 font-sans text-xs font-semibold disabled:opacity-50"
            >
              {paynowMut.isPending ? 'Sending…' : 'Send pay-now emails'}
            </button>
          </div>
          <div className="space-y-3 border border-border-soft rounded-sm p-4">
            <h3 className="font-sans text-sm font-semibold text-slate">Custom mail (HTML)</h3>
            <input
              value={customSubject}
              onChange={(e) => setCustomSubject(e.target.value)}
              placeholder="Subject"
              className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
            />
            <textarea
              value={customBody}
              onChange={(e) => setCustomBody(e.target.value)}
              placeholder="<p>HTML body</p>"
              rows={4}
              className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm font-mono text-xs"
            />
            <select
              value={customSub}
              onChange={(e) => setCustomSub(e.target.value)}
              className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
            >
              <option value="">All paid (Credit) batches</option>
              {activeBatches.map((b) => (
                <option key={b.id} value={b.name}>
                  {b.name}
                </option>
              ))}
            </select>
            <input
              type="number"
              min={1}
              max={500}
              value={customLimit}
              onChange={(e) => setCustomLimit(e.target.value)}
              className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
              placeholder="Max recipients"
            />
            <button
              type="button"
              disabled={!customSubject.trim() || !customBody.trim() || customMut.isPending}
              onClick={() => {
                if (!window.confirm('Send this HTML email to matching Credit users?')) return;
                customMut.mutate();
              }}
              className="magnetic bg-slate text-chalk rounded-sm px-4 py-2 font-sans text-xs font-semibold disabled:opacity-50"
            >
              {customMut.isPending ? 'Sending…' : 'Send custom emails'}
            </button>
          </div>
          <div className="space-y-3 border border-border-soft rounded-sm p-4 md:col-span-3">
            <h3 className="font-sans text-sm font-semibold text-slate">Batch-wise email templates</h3>
            <p className="text-xs text-ink-muted">
              Configure one template per batch and event. Write normal text (no HTML required). Supported placeholders:{' '}
              {'{{name}}'}, {'{{email}}'}, {'{{subscription}}'}, {'{{batch_name}}'}, {'{{dashboard_url}}'}, {'{{login_url}}'},{' '}
              {'{{status_label}}'}.
            </p>
            <div className="grid gap-3 md:grid-cols-4">
              <select
                value={tplBatchId}
                onChange={(e) => setTplBatchId(e.target.value)}
                className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
              >
                {activeBatches.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
              <select
                value={tplType}
                onChange={(e) => setTplType(e.target.value as EmailTemplateType)}
                className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
              >
                <option value="registration_thank_you">Registration Thank You</option>
                <option value="document_verified">Document Verified</option>
                <option value="document_denied">Document Denied</option>
              </select>
              <select
                value={tplStatus}
                onChange={(e) => setTplStatus(e.target.value === '0' ? '0' : '1')}
                className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
              >
                <option value="1">Active</option>
                <option value="0">Inactive</option>
              </select>
              <input
                value={tplSubject}
                onChange={(e) => setTplSubject(e.target.value)}
                placeholder="Template subject"
                className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
              />
            </div>
            <textarea
              value={tplBody}
              onChange={(e) => setTplBody(e.target.value)}
              placeholder={'Write your email message here.\n\nExample:\nDear {{name}},\nYour registration for {{batch_name}} is confirmed.'}
              rows={8}
              className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm font-mono text-xs"
            />
            <div className="border border-border-soft rounded-sm bg-chalk-warm px-3 py-2">
              <p className="font-mono text-[10px] uppercase tracking-wide text-ink-faint mb-1">Preview (plain text view)</p>
              <div className="text-xs text-ink whitespace-pre-wrap min-h-[56px]">
                {tplBody.trim() || 'Template content preview will appear here.'}
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                disabled={!tplBatchId || !tplSubject.trim() || !tplBody.trim() || saveTemplateMut.isPending}
                onClick={() => saveTemplateMut.mutate()}
                className="magnetic bg-slate text-chalk rounded-sm px-4 py-2 font-sans text-xs font-semibold disabled:opacity-50"
              >
                {saveTemplateMut.isPending ? 'Saving…' : tplId ? 'Update template' : 'Create template'}
              </button>
              <button
                type="button"
                disabled={!tplId || deleteTemplateMut.isPending}
                onClick={() => {
                  if (!tplId) return;
                  if (!window.confirm('Delete this template for the selected batch and event?')) return;
                  deleteTemplateMut.mutate(tplId);
                }}
                className="magnetic bg-blush text-chalk rounded-sm px-4 py-2 font-sans text-xs font-semibold disabled:opacity-50"
              >
                {deleteTemplateMut.isPending ? 'Deleting…' : 'Delete template'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setTplId(null);
                  setTplStatus('1');
                  setTplSubject('');
                  setTplBody('');
                }}
                className="magnetic border border-border-strong text-slate rounded-sm px-4 py-2 font-sans text-xs font-semibold"
              >
                Clear form
              </button>
            </div>
          </div>
        </div>
      </section>

      <div className="bg-chalk border border-border-soft rounded-sm shadow-sm w-full min-w-0">
        <div className="overflow-x-auto overscroll-x-auto [-webkit-overflow-scrolling:touch]">
          <table className="w-full border-collapse min-w-[2920px] text-left">
            <thead>
              <tr className="bg-chalk-cool border-b border-border-soft">
                {[
                  { id: 'id', label: 'ID' },
                  { id: 'registration_type', label: 'Type' },
                  { id: 'subscription', label: 'Batch' },
                  { label: 'Plan type' },
                  { label: 'Course start' },
                  { label: 'Course end' },
                  { label: 'Access' },
                  { id: 'name', label: 'Name' },
                  { id: 'email', label: 'Email' },
                  { label: 'Password' },
                  { id: 'contact_number', label: 'Phone' },
                  { label: 'Organization' },
                  { label: 'Qual.' },
                  { label: 'Specialty' },
                  { label: 'Country' },
                  { label: 'State' },
                  { label: 'City' },
                  { label: 'PIN' },
                  { label: 'Documents' },
                  { label: 'Amount' },
                  { id: 'payment_status', label: 'Payment' },
                  { label: 'Txn ID' },
                  { id: 'created_at', label: 'Registered' },
                  { label: 'Mail' },
                  { id: 'approve', label: 'Account' },
                  { label: 'Mock' },
                  { label: 'Actions' },
                ].map((h) => (
                  <th
                    key={typeof h === 'string' ? h : h.label}
                    onClick={() => 'id' in h && h.id && toggleSort(h.id)}
                    className={`font-mono text-xs text-ink-faint uppercase tracking-[0.12em] px-3 py-3 whitespace-nowrap align-bottom ${
                      'id' in h ? 'cursor-pointer hover:text-ink transition-colors' : ''
                    }`}
                  >
                    {h.label}
                    {'id' in h && <SortIcon field={h.id!} />}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={COL_COUNT} className="px-6 py-12 text-center font-mono text-xs text-ink-faint animate-pulse">
                    Refreshing user records...
                  </td>
                </tr>
              )}
              {error && (
                <tr>
                  <td colSpan={COL_COUNT} className="px-6 py-12 text-center font-sans text-sm text-red-500">
                    Error loading users: {error instanceof Error ? error.message : 'Unknown error'}
                  </td>
                </tr>
              )}
              {!isLoading && users.length === 0 && (
                <tr>
                  <td colSpan={COL_COUNT} className="px-6 py-12 text-center font-sans text-sm text-ink-muted">
                    No users found matching your criteria.
                  </td>
                </tr>
              )}
              {users.map((u) => {
                const pay = (u.payment_status || '').toLowerCase();
                const isCredit = pay === 'credit';
                const approved = String(u.approve ?? '') === '1';
                const hasDoc = !!(u.document_file && String(u.document_file).trim());
                const docStatus = String(u.document_file_status ?? '0');
                const url1 = resolveDocUrl(u, 1);
                const url2 = resolveDocUrl(u, 2);
                const canSendMail = isCredit && approved && u.has_password;
                const showRefundDeactive = isCredit && approved;
                const showPaymentActions = !isCredit;
                const access = u.subscription_access;

                return (
                  <tr key={u.id} className="border-b border-border-soft hover:bg-ink-ghost transition-colors align-top">
                    <td className="px-3 py-2 font-mono text-xs text-ink-faint whitespace-nowrap">#{u.id}</td>
                    <td className="px-3 py-2 font-mono text-xs text-ink-muted max-w-[72px] truncate" title={u.registration_type || ''}>
                      {u.registration_type || '—'}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-ink-muted max-w-[100px] truncate" title={u.subscription || ''}>
                      {u.subscription || '—'}
                    </td>
                    <td
                      className="px-3 py-2 font-sans text-xs text-ink-muted max-w-[120px] truncate"
                      title={[access?.plan_type_label, access?.package_name].filter(Boolean).join(' · ') || ''}
                    >
                      <div className="leading-snug">{access?.plan_type_label || '—'}</div>
                      {access?.package_name ? (
                        <div className="font-mono text-[10px] text-ink-faint truncate">{access.package_name}</div>
                      ) : null}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs whitespace-nowrap text-ink-muted">
                      {formatCourseDate(access?.course_start_at)}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs whitespace-nowrap text-ink-muted">
                      <div>{formatCourseDate(access?.course_end_at)}</div>
                      {typeof access?.days_remaining === 'number' && access.access_status === 'active' ? (
                        <div className="text-[10px] text-ink-faint">{access.days_remaining}d left</div>
                      ) : null}
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap">
                      <span
                        className={`inline-block font-mono text-[10px] font-bold px-2 py-0.5 rounded-sm border uppercase tracking-wide ${accessStatusClasses(access?.access_status)}`}
                      >
                        {accessStatusLabel(access?.access_status)}
                      </span>
                    </td>
                    <td className="px-3 py-2 min-w-[120px]">
                      <Link to={`/admin/users/${u.id}`} className="font-sans text-xs font-semibold text-ink hover:text-mint leading-snug">
                        {displayName(u)}
                      </Link>
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-slate min-w-[232px] max-w-[280px] align-top break-all leading-snug select-all [overflow-wrap:anywhere]">
                      {u.email || '—'}
                    </td>
                    <td className="px-3 py-2 font-mono text-[11px] text-ink-faint max-w-[280px] leading-snug break-all [overflow-wrap:anywhere] select-all">
                      {encryptedPasswordById[u.id] || encryptedPasswordValue(u) || '—'}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs whitespace-nowrap">{u.contact_number || '—'}</td>
                    <td className="px-3 py-2 font-sans text-xs text-ink-muted max-w-[120px] truncate" title={u.hospital || ''}>
                      {u.hospital || '—'}
                    </td>
                    <td className="px-3 py-2 font-sans text-xs max-w-[100px] truncate" title={u.qualification || ''}>
                      {u.qualification || '—'}
                    </td>
                    <td className="px-3 py-2 font-sans text-xs max-w-[110px] truncate" title={u.speciality || ''}>
                      {u.speciality || '—'}
                    </td>
                    <td className="px-3 py-2 font-sans text-xs max-w-[90px] truncate">{u.country_name || '—'}</td>
                    <td className="px-3 py-2 font-sans text-xs max-w-[90px] truncate">{u.state || '—'}</td>
                    <td className="px-3 py-2 font-sans text-xs max-w-[90px] truncate">{u.city || '—'}</td>
                    <td className="px-3 py-2 font-mono text-xs">{u.pin_code || '—'}</td>
                    <td className="px-3 py-2 min-w-[200px]">
                      <div className="flex flex-col gap-1.5">
                        {hasDoc && (
                          <div className="flex flex-wrap gap-1">
                            {url1 ? (
                              <a
                                href={url1}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-block text-xs font-bold px-3 py-1 rounded-sm bg-slate text-chalk border border-slate hover:bg-slate-light"
                              >
                                View file 1
                              </a>
                            ) : (
                              <span className="text-[10px] text-ink-faint" title="No URL for this file — check S3 or LEGACY_UPLOAD_BASE_URL">
                                File 1
                              </span>
                            )}
                            {u.document_file_2?.trim() ? (
                              url2 ? (
                                <a
                                  href={url2}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-block text-xs font-bold px-3 py-1 rounded-sm bg-slate text-chalk border border-slate hover:bg-slate-light"
                                >
                                  View file 2
                                </a>
                              ) : (
                                <span className="text-[10px] text-ink-faint">File 2</span>
                              )
                            ) : null}
                          </div>
                        )}
                        {!hasDoc && (
                          <span className="text-[10px] text-ink-faint italic mb-1">No docs uploaded</span>
                        )}
                        <select
                          value={docStatus}
                          disabled={docMut.isPending || !hasDoc}
                          onChange={(e) => {
                            const v = e.target.value;
                            if (v === '0') return;
                            const msg =
                              v === '1'
                                ? `Approve document for ${displayName(u)}? Account will be marked approved.`
                                : `Deny document for ${displayName(u)}?`;
                            if (!window.confirm(msg)) return;
                            docMut.mutate({ userId: u.id, document_file_status: v });
                          }}
                          className="w-full max-w-[140px] bg-chalk-warm border border-border-soft rounded-sm py-1 px-1.5 font-sans text-[11px]"
                        >
                          <option value="0">{hasDoc ? 'Review…' : 'No doc'}</option>
                          <option value="1">Approve doc</option>
                          <option value="2">Deny doc</option>
                        </select>
                        {docStatus === '1' && (
                          <span className="text-[10px] text-mint font-mono">Doc OK</span>
                        )}
                      </div>
                    </td>
                    <td className="px-3 py-2 font-mono text-xs whitespace-nowrap">
                      {(u.currency_name || '').trim()} {u.total_amount != null ? Number(u.total_amount).toFixed(2) : '—'}
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap">
                      <span
                        className={`font-mono text-xs font-bold uppercase tracking-wider border rounded-full px-2.5 py-1 inline-block ${paymentBadgeClasses(
                          u.payment_status || 'pending',
                        )}`}
                      >
                        {paymentBadgeLabel(u.payment_status)}
                      </span>
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-ink-faint max-w-[120px] truncate" title={u.payment_id || ''}>
                      {u.payment_id?.trim() || '—'}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-ink-faint whitespace-nowrap">{formatLegacyDateTime(u.created_at)}</td>
                    <td className="px-3 py-2">
                      {canSendMail ? (
                        <button
                          type="button"
                          disabled={pwdMailMut.isPending}
                          onClick={() => pwdMailMut.mutate(u.id)}
                          className="text-xs font-bold px-3 py-1 rounded-sm bg-slate text-chalk border border-slate hover:bg-slate-light disabled:opacity-50"
                        >
                          {pwdMailMut.isPending ? 'Sending…' : 'Send mail'}
                        </button>
                      ) : (
                        <span className="text-[10px] text-ink-faint">—</span>
                      )}
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap">
                      {approved ? (
                        <span className="font-mono text-xs uppercase tracking-wider border rounded-full px-2 py-0.5 bg-mint-pale border-mint/25 text-mint">
                          Active
                        </span>
                      ) : (
                        <span className="font-mono text-xs uppercase tracking-wider border rounded-full px-2 py-0.5 bg-blush/15 border-blush/35 text-blush">
                          Deactive
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap min-w-[100px]">
                      {(() => {
                        const info = u.mock_test_attempts;
                        if (!info) return <span className="text-[10px] text-ink-faint">—</span>;
                        const source =
                          info.user_override != null
                            ? `user ${info.user_override}`
                            : info.batch_override != null
                              ? `batch ${info.batch_override}`
                              : `default ${info.default_max_attempts}`;
                        return (
                          <div className="flex flex-col gap-1">
                            <span className="font-mono text-[10px] text-ink-muted">
                              {info.effective_max_attempts} max
                            </span>
                            <span className="font-mono text-[9px] text-ink-faint">{source}</span>
                            <button
                              type="button"
                              onClick={() => openAttemptsDialog(u)}
                              className="text-[10px] font-semibold text-mint hover:underline w-fit text-left"
                            >
                              Edit
                            </button>
                          </div>
                        );
                      })()}
                    </td>
                    <td className="px-3 py-2 min-w-[200px]">
                      <div className="flex flex-col gap-1">
                        {showPaymentActions && (
                          <div className="flex flex-col gap-1">
                            <button
                              type="button"
                              disabled={syncRazorpayMut.isPending}
                              onClick={() => {
                                if (!window.confirm(`Sync Razorpay payment for user #${u.id}?`)) return;
                                syncRazorpayMut.mutate(u.id);
                              }}
                              className="text-[10px] font-semibold px-2 py-0.5 rounded-sm bg-mint-pale text-mint border border-mint/30 hover:bg-mint/20 disabled:opacity-50 w-fit"
                            >
                              Sync Razorpay
                            </button>
                            <button
                              type="button"
                              disabled={offlineCreditMut.isPending}
                              onClick={() => {
                                if (!window.confirm(`Mark user #${u.id} as paid (offline credit)?`)) return;
                                offlineCreditMut.mutate(u.id);
                              }}
                              className="text-[10px] font-semibold px-2 py-0.5 rounded-sm bg-slate/10 text-slate border border-border-strong hover:bg-chalk-cool disabled:opacity-50 w-fit"
                            >
                              Mark paid
                            </button>
                            <Link
                              to={`/admin/users/${u.id}`}
                              className="text-[10px] text-ink-faint hover:text-mint underline w-fit"
                            >
                              User detail
                            </Link>
                          </div>
                        )}
                        {showRefundDeactive && (
                          <div className="flex flex-wrap gap-1">
                            <button
                              type="button"
                              disabled={refundMut.isPending}
                              onClick={() => {
                                if (!window.confirm(`Refund user #${u.id}?`)) return;
                                refundMut.mutate(u.id);
                              }}
                              className="text-[10px] font-semibold px-2 py-0.5 rounded-sm bg-amber-50 text-amber-900 border border-amber-200 hover:bg-amber-100 disabled:opacity-50"
                            >
                              Refund
                            </button>
                            <button
                              type="button"
                              disabled={approveMut.isPending}
                              onClick={() => {
                                if (!window.confirm(`Deactivate user #${u.id}?`)) return;
                                approveMut.mutate({ userId: u.id, approve: '0' });
                              }}
                              className="text-[10px] font-semibold px-2 py-0.5 rounded-sm bg-blush/15 text-blush border border-blush/40 hover:bg-blush/25 disabled:opacity-50"
                            >
                              Deactive
                            </button>
                          </div>
                        )}
                        {!approved && (
                          <button
                            type="button"
                            disabled={approveMut.isPending}
                            onClick={() => {
                              if (!isCredit && !window.confirm('User has not paid yet (Credit status). Approve access anyway?')) return;
                              approveMut.mutate({ userId: u.id, approve: '1' });
                            }}
                            className="text-[10px] font-semibold px-2 py-0.5 rounded-sm bg-mint-pale text-mint border border-mint/30 hover:bg-mint/20 w-fit disabled:opacity-50"
                          >
                            Approve access
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between px-6 py-4 bg-chalk-cool border-t border-border-soft">
          <div className="font-mono text-xs text-ink-faint">
            SHOWING {users.length} OF {total} ENTRIES
          </div>
          {total > limit && (
            <div className="flex items-center gap-2">
              <button
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - limit))}
                className="p-1.5 border border-border-strong rounded-sm hover:bg-chalk disabled:opacity-30 cursor-pointer"
              >
                <ChevronLeft size={16} />
              </button>
              <button
                disabled={offset + limit >= total}
                onClick={() => setOffset(offset + limit)}
                className="p-1.5 border border-border-strong rounded-sm hover:bg-chalk disabled:opacity-30 cursor-pointer"
              >
                <ChevronRight size={16} />
              </button>
            </div>
          )}
        </div>
      </div>

      <Dialog open={!!attemptsUser} onOpenChange={(open) => !open && setAttemptsUser(null)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Mock test attempts</DialogTitle>
          </DialogHeader>
          {attemptsUser && (
            <div className="space-y-4 font-sans text-sm">
              <p className="text-ink-muted">
                User: <span className="font-semibold text-ink">{displayName(attemptsUser)}</span>
                <br />
                <span className="font-mono text-xs">{attemptsUser.email}</span>
              </p>
              {attemptsUser.mock_test_attempts && (
                <p className="font-mono text-[11px] text-ink-faint">
                  Current effective limit: {attemptsUser.mock_test_attempts.effective_max_attempts}
                  {attemptsUser.mock_test_attempts.user_override != null
                    ? ` (user override)`
                    : attemptsUser.mock_test_attempts.batch_override != null
                      ? ` (batch override)`
                      : ` (site default)`}
                </p>
              )}
              <label className="block text-ink-secondary">
                Max attempts (1–50)
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={attemptsInput}
                  onChange={(e) => setAttemptsInput(e.target.value)}
                  className="mt-2 w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-mono text-sm"
                />
              </label>
              <p className="text-xs text-ink-faint">
                Clear the field and save to remove the per-user override (batch/default will apply).
              </p>
            </div>
          )}
          <DialogFooter className="gap-2 sm:gap-0">
            <Button type="button" variant="outline" onClick={() => setAttemptsUser(null)}>
              Cancel
            </Button>
            <Button type="button" disabled={mockAttemptsMut.isPending} onClick={saveUserAttempts}>
              {mockAttemptsMut.isPending ? 'Saving…' : 'Save'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
