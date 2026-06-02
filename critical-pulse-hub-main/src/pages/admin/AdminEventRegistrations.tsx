import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { apiClient } from '@/lib/apiClient';
import { downloadAuthenticatedFile } from '@/lib/apiBase';
import { EVENT_DISPLAY_NAME } from '@/lib/eventConclave';

type EventRow = {
  id: number;
  registration_number: string;
  full_name: string;
  email: string;
  phone: string;
  category: string;
  payment_status: string;
  amount_inr: number;
  city: string;
  state: string;
  created_at: string | null;
};

type PaymentTxn = {
  request_id?: string;
  gateway_order_id?: string | null;
  gateway_payment_id?: string | null;
  gateway_status?: string | null;
  is_finalized?: string | null;
  amount?: number;
  currency?: string | null;
};

type EventDetail = EventRow & {
  designation?: string;
  specialty?: string;
  country_name?: string;
  hospital?: string;
  council_state?: string;
  council_registration_number?: string;
  payment_id?: string | null;
  payment_type?: string | null;
  payment_date?: string | null;
  payment_txn?: PaymentTxn | null;
};

function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatCategory(value: string | null | undefined): string {
  if (value === 'clinician') return 'Practicing Clinician';
  if (value === 'student') return 'Student';
  return value || '—';
}

function isPendingPayment(status: string | null | undefined): boolean {
  const v = (status || '').trim().toLowerCase();
  return v === 'pending' || v === '';
}

function isPaidPayment(status: string | null | undefined): boolean {
  return (status || '').trim().toLowerCase() === 'credit';
}

function formatPaymentStatus(value: string | null | undefined): string {
  const v = (value || '').trim().toLowerCase();
  if (v === 'credit') return 'Paid (Credit)';
  if (v === 'pending') return 'Pending';
  if (v === 'failed') return 'Failed';
  return value || '—';
}

function formatGatewayStatus(value: string | null | undefined): string {
  const v = (value || '').trim().toLowerCase();
  if (v === 'waived') return 'Waived — promo / free registration';
  if (v === 'paid') return 'Paid';
  if (v === 'order_created') return 'Razorpay order created';
  if (v === 'created') return 'Created';
  if (v === 'signature_failed') return 'Signature verification failed';
  return value || '—';
}

function formatFinalized(value: string | null | undefined): string {
  return (value || '').trim() === '1' ? 'Yes' : 'No';
}

function formatAmount(amount: number | undefined, currency: string | null | undefined): string {
  const cur = (currency || 'INR').toUpperCase();
  const n = Number(amount ?? 0);
  if (cur === 'INR') {
    return `₹ ${n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
  return `${cur} ${n.toLocaleString()}`;
}

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-1 sm:gap-2 py-2 border-b border-border-soft last:border-0">
      <dt className="text-ink-faint font-sans text-sm">{label}</dt>
      <dd className="text-slate font-sans text-sm break-words">{value ?? '—'}</dd>
    </div>
  );
}

function DetailSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-6">
      <h3 className="font-display font-semibold text-slate text-sm mb-2 uppercase tracking-wide">{title}</h3>
      <dl>{children}</dl>
    </section>
  );
}

export default function AdminEventRegistrations() {
  const [q, setQ] = useState('');
  const [paymentStatus, setPaymentStatus] = useState('');
  const [category, setCategory] = useState('');
  const [page, setPage] = useState(1);
  const pageSize = 25;
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const queryClient = useQueryClient();

  const approveMutation = useMutation({
    mutationFn: (payload: { id: number; force_manual?: boolean; resend_email?: boolean }) =>
      apiClient(`/admin/events/registrations/${payload.id}/approve`, {
        method: 'POST',
        body: JSON.stringify({
          force_manual: payload.force_manual ?? false,
          resend_email: payload.resend_email ?? false,
        }),
      }) as Promise<{ message?: string; email_sent?: boolean; payment_status?: string }>,
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ['adminEventRegistrations'] });
      void queryClient.invalidateQueries({ queryKey: ['adminEventRegistrationDetail'] });
      toast.success(
        result.email_sent
          ? result.message || 'Approved and confirmation email sent'
          : result.message || 'Approved (email could not be sent — check SMTP)',
      );
    },
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : 'Approval failed');
    },
  });

  const handleApprove = async (id: number, forceManual = false) => {
    if (
      forceManual &&
      !window.confirm(
        'Razorpay could not verify this payment. Mark as paid manually and send the confirmation email?',
      )
    ) {
      return;
    }
    try {
      await approveMutation.mutateAsync({ id, force_manual: forceManual });
    } catch {
      if (!forceManual) {
        const retry = window.confirm(
          'Could not verify payment on Razorpay. Approve manually anyway and send confirmation email?',
        );
        if (retry) {
          await handleApprove(id, true);
        }
      }
    }
  };
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['adminEventRegistrations', q, paymentStatus, category, page],
    queryFn: () => {
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
      });
      if (q.trim()) params.set('q', q.trim());
      if (paymentStatus) params.set('payment_status', paymentStatus);
      if (category) params.set('category', category);
      return apiClient(`/admin/events/registrations?${params.toString()}`);
    },
  });

  const { data: detail } = useQuery({
    queryKey: ['adminEventRegistrationDetail', selectedId],
    queryFn: () => apiClient(`/admin/events/registrations/${selectedId}`),
    enabled: selectedId != null,
  }) as { data: EventDetail | undefined };

  const items: EventRow[] = data?.items ?? [];
  const total: number = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const exportExcel = async () => {
    try {
      const params = paymentStatus ? `?payment_status=${encodeURIComponent(paymentStatus)}` : '';
      await downloadAuthenticatedFile(
        `/admin/events/registrations/export.xlsx${params}`,
        `event-registrations-${new Date().toISOString().slice(0, 10)}.xlsx`,
      );
      toast.success('Excel file downloaded');
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : 'Export failed');
    }
  };

  return (
    <div className="p-6 lg:p-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="font-display font-bold text-3xl text-slate">Event registrations</h1>
          <p className="font-mono text-[11px] text-ink-faint mt-1 uppercase tracking-wider">
            {EVENT_DISPLAY_NAME} — 11–12 July 2026
          </p>
        </div>
        <button
          type="button"
          onClick={() => void exportExcel()}
          className="magnetic bg-slate text-chalk rounded-sm px-5 py-2.5 font-sans text-xs font-semibold hover:bg-slate-light"
        >
          Download Excel
        </button>
      </div>

      <div className="flex flex-col sm:flex-row flex-wrap gap-3 mb-6">
        <input
          type="search"
          placeholder="Search name, email, registration no…"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(1);
          }}
          className="flex-1 min-w-[200px] bg-chalk border border-border-soft rounded-sm py-2.5 px-3 font-sans text-sm"
        />
        <select
          value={paymentStatus}
          onChange={(e) => {
            setPaymentStatus(e.target.value);
            setPage(1);
          }}
          className="bg-chalk border border-border-soft rounded-sm py-2.5 px-3 font-sans text-sm"
        >
          <option value="">All payment status</option>
          <option value="Credit">Paid (Credit)</option>
          <option value="Pending">Pending</option>
          <option value="Failed">Failed</option>
        </select>
        <select
          value={category}
          onChange={(e) => {
            setCategory(e.target.value);
            setPage(1);
          }}
          className="bg-chalk border border-border-soft rounded-sm py-2.5 px-3 font-sans text-sm"
        >
          <option value="">All categories</option>
          <option value="clinician">Clinician</option>
          <option value="student">Student</option>
        </select>
        <button
          type="button"
          onClick={() => void refetch()}
          className="border border-border-soft rounded-sm px-4 py-2 font-sans text-xs hover:border-border-strong"
        >
          Refresh
        </button>
      </div>

      {error && (
        <p className="text-red-600 font-sans text-sm mb-4">
          {error instanceof Error ? error.message : 'Failed to load'}
        </p>
      )}

      <div className="overflow-x-auto border border-border-soft rounded-sm bg-chalk">
        <table className="w-full font-sans text-sm">
          <thead>
            <tr className="border-b border-border-soft bg-chalk-stone text-left text-[11px] uppercase tracking-wider text-ink-faint">
              <th className="p-3">Reg. no.</th>
              <th className="p-3">Name</th>
              <th className="p-3">Email</th>
              <th className="p-3">Category</th>
              <th className="p-3">Amount</th>
              <th className="p-3">Status</th>
              <th className="p-3"></th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={7} className="p-8 text-center text-ink-muted">
                  Loading…
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={7} className="p-8 text-center text-ink-muted">
                  No registrations yet
                </td>
              </tr>
            ) : (
              items.map((row) => (
                <tr key={row.id} className="border-b border-border-soft hover:bg-chalk-warm/50">
                  <td className="p-3 font-mono text-xs">{row.registration_number}</td>
                  <td className="p-3">{row.full_name}</td>
                  <td className="p-3">{row.email}</td>
                  <td className="p-3 capitalize">{row.category}</td>
                  <td className="p-3">₹ {row.amount_inr?.toLocaleString('en-IN')}</td>
                  <td className="p-3">
                    <span
                      className={`inline-block px-2 py-0.5 rounded text-xs ${
                        (row.payment_status || '').toLowerCase() === 'credit'
                          ? 'bg-mint-pale text-slate'
                          : 'bg-chalk-stone text-ink-muted'
                      }`}
                    >
                      {row.payment_status || '—'}
                    </span>
                  </td>
                  <td className="p-3">
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        className="text-mint text-xs hover:underline"
                        onClick={() => setSelectedId(row.id)}
                      >
                        View
                      </button>
                      {isPendingPayment(row.payment_status) && (
                        <button
                          type="button"
                          className="text-slate text-xs font-semibold hover:underline disabled:opacity-50"
                          disabled={approveMutation.isPending}
                          onClick={() => void handleApprove(row.id)}
                        >
                          Approve
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between mt-4 font-sans text-sm text-ink-muted">
        <span>
          {total} total · page {page} of {totalPages}
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            className="border border-border-soft rounded-sm px-3 py-1 disabled:opacity-40"
          >
            Previous
          </button>
          <button
            type="button"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
            className="border border-border-soft rounded-sm px-3 py-1 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      </div>

      {selectedId != null && detail && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate/40"
          onClick={() => setSelectedId(null)}
        >
          <div
            className="bg-chalk max-w-lg w-full max-h-[85vh] overflow-y-auto rounded-sm border border-border-soft p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="font-display font-bold text-xl text-slate mb-1">Registration detail</h2>
            <p className="font-mono text-xs text-mint mb-6">{detail.registration_number}</p>

            <DetailSection title="Personal details">
              <DetailRow label="Full name" value={detail.full_name} />
              <DetailRow label="Designation" value={detail.designation} />
              <DetailRow label="Category" value={formatCategory(detail.category)} />
              <DetailRow label="Specialty" value={detail.specialty} />
              <DetailRow label="Email" value={detail.email} />
              <DetailRow label="Phone" value={detail.phone} />
              <DetailRow label="Country" value={detail.country_name} />
              <DetailRow label="Hospital / Institution" value={detail.hospital} />
              <DetailRow label="City" value={detail.city} />
              <DetailRow label="State" value={detail.state} />
            </DetailSection>

            <DetailSection title="Council details">
              <DetailRow label="Council state" value={detail.council_state} />
              <DetailRow label="Council registration no." value={detail.council_registration_number} />
            </DetailSection>

            <DetailSection title="Payment summary">
              <DetailRow label="Amount paid" value={formatAmount(detail.amount_inr, 'INR')} />
              <DetailRow label="Payment status" value={formatPaymentStatus(detail.payment_status)} />
              <DetailRow label="Payment method" value={detail.payment_type || '—'} />
              <DetailRow
                label="Payment reference"
                value={
                  detail.payment_type?.toLowerCase() === 'promo'
                    ? `Promo code: ${detail.payment_id || '—'}`
                    : detail.payment_id || '—'
                }
              />
              <DetailRow label="Payment date" value={formatDateTime(detail.payment_date)} />
              <DetailRow label="Registered on" value={formatDateTime(detail.created_at)} />
            </DetailSection>

            {detail.payment_txn && (
              <DetailSection title="Payment transaction">
                <DetailRow label="Transaction status" value={formatGatewayStatus(detail.payment_txn.gateway_status)} />
                <DetailRow
                  label="Amount"
                  value={formatAmount(detail.payment_txn.amount, detail.payment_txn.currency)}
                />
                <DetailRow label="Currency" value={(detail.payment_txn.currency || 'INR').toUpperCase()} />
                <DetailRow label="Finalized" value={formatFinalized(detail.payment_txn.is_finalized)} />
                <DetailRow label="Request ID" value={detail.payment_txn.request_id} />
                <DetailRow label="Razorpay order ID" value={detail.payment_txn.gateway_order_id || '—'} />
                <DetailRow label="Razorpay payment ID" value={detail.payment_txn.gateway_payment_id || '—'} />
              </DetailSection>
            )}

            {isPendingPayment(detail.payment_status) && (
              <button
                type="button"
                className="mt-2 w-full bg-slate text-chalk py-2.5 rounded-sm font-sans text-sm font-semibold hover:bg-slate-light disabled:opacity-50"
                disabled={approveMutation.isPending}
                onClick={() => void handleApprove(detail.id)}
              >
                {approveMutation.isPending ? 'Approving…' : 'Approve payment & send email'}
              </button>
            )}

            {isPaidPayment(detail.payment_status) && (
              <button
                type="button"
                className="mt-2 w-full border border-border-soft py-2 rounded-sm font-sans text-sm disabled:opacity-50"
                disabled={approveMutation.isPending}
                onClick={() =>
                  void approveMutation.mutateAsync({ id: detail.id, force_manual: false, resend_email: true })
                }
              >
                Resend confirmation email
              </button>
            )}

            <button
              type="button"
              className="mt-2 w-full border border-border-soft py-2 rounded-sm font-sans text-sm"
              onClick={() => setSelectedId(null)}
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
