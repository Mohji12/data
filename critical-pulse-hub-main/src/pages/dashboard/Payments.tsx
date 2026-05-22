import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/apiClient';

type DashboardPayment = {
  id: number | string;
  payment_date?: string | null;
  date?: string | null;
  course?: string | null;
  package_name?: string | null;
  subscription?: string | null;
  package_type?: string | null;
  amount?: number | string | null;
  paid_amount?: number | string | null;
  method?: string | null;
  payment_method?: string | null;
  payment_type?: string | null;
  status?: string | null;
  payment_status?: string | null;
};

function normalizeAmount(value: number | string | null | undefined): number {
  if (typeof value === 'number') return Number.isFinite(value) ? value : 0;
  if (typeof value === 'string') {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
}

export default function Payments() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboardPayments'],
    queryFn: () => apiClient('/dashboard/payments') as Promise<DashboardPayment[] | { items?: DashboardPayment[] }>,
    refetchInterval: 15000,
  });

  const payments = Array.isArray(data) ? data : data?.items || [];

  if (isLoading) {
    return <div className="p-6 lg:p-8 font-mono text-xs text-ink-faint animate-pulse">Loading payments...</div>;
  }

  if (error) {
    return (
      <div className="p-6 lg:p-8">
        <h1 className="font-display font-bold text-3xl text-slate mb-4">Payments</h1>
        <p className="font-sans text-sm text-red-600">{error instanceof Error ? error.message : 'Unable to load payments'}</p>
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8">
      <h1 className="font-display font-bold text-3xl text-slate mb-8">Payments</h1>
      <div className="bg-chalk border border-border-soft rounded-sm overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="bg-chalk-cool">
              <th className="font-mono text-xs text-ink-faint uppercase tracking-[0.1em] text-left px-6 py-3">Date</th>
              <th className="font-mono text-xs text-ink-faint uppercase tracking-[0.1em] text-left px-6 py-3">Course</th>
              <th className="font-mono text-xs text-ink-faint uppercase tracking-[0.1em] text-left px-6 py-3">Amount</th>
              <th className="font-mono text-xs text-ink-faint uppercase tracking-[0.1em] text-left px-6 py-3">Method</th>
              <th className="font-mono text-xs text-ink-faint uppercase tracking-[0.1em] text-left px-6 py-3">Status</th>
            </tr>
          </thead>
          <tbody>
            {payments.length === 0 && (
              <tr>
                <td colSpan={5} className="px-6 py-8 text-center font-sans text-sm text-ink-muted">
                  No payments found yet.
                </td>
              </tr>
            )}
            {payments.map((p) => {
              const rawStatus = String(p.payment_status ?? p.status ?? 'pending').toLowerCase();
              const isPaid = rawStatus === 'paid' || rawStatus === 'success';
              const dateText = p.payment_date ?? p.date ?? '—';
              const courseText = p.package_name ?? p.course ?? p.subscription ?? p.package_type ?? '—';
              const rawAmount = p.amount ?? p.paid_amount;
              const amount = normalizeAmount(rawAmount);
              const methodText = p.payment_method ?? p.method ?? p.payment_type ?? '—';
              return (
                <tr key={p.id} className="border-b border-border-soft hover:bg-ink-ghost transition-colors">
                  <td className="px-6 py-4 font-mono text-xs text-ink-muted">{dateText || '—'}</td>
                  <td className="px-6 py-4 font-sans text-sm text-ink-secondary">{courseText}</td>
                  <td className="px-6 py-4 font-display font-bold text-lg text-slate">{rawAmount == null ? '—' : `₹${amount.toLocaleString()}`}</td>
                  <td className="px-6 py-4 font-mono text-xs text-ink-faint">{methodText}</td>
                  <td className="px-6 py-4">
                    <span className={`font-mono text-xs font-bold border rounded-sm px-2.5 py-1 ${isPaid ? 'border-mint/30 text-mint' : 'border-amber/30 text-amber'}`}>
                      {rawStatus}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
