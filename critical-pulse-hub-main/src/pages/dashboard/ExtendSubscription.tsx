import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { apiClient } from '@/lib/apiClient';
import { useAuthStore } from '@/store/authStore';

interface ExtensionOffer {
  enabled: boolean;
  reason?: string;
  days_to_expiry?: number;
  current_end_at?: string;
  extension_months: number;
  estimated_amount?: number;
  currency_name?: string;
  payment_amount_inr?: number;
  display_amount_usd?: number;
  gross_amount?: number;
  gst_percentage?: number;
  gst_amount?: number;
  batch_end_date?: string;
  extended_end_date?: string;
  headline?: string;
}

function formatDisplayDate(iso: string | undefined): string {
  if (!iso) return '';
  const d = new Date(`${iso}T12:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' });
}

export default function ExtendSubscription() {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const [loading, setLoading] = useState(false);
  const [offerLoading, setOfferLoading] = useState(true);
  const [offer, setOffer] = useState<ExtensionOffer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeRequestId, setActiveRequestId] = useState<string | null>(null);
  const [showOfflineForm, setShowOfflineForm] = useState(false);
  const [offlineReference, setOfflineReference] = useState('');
  const [offlineNote, setOfflineNote] = useState('');
  const [offlineSubmitting, setOfflineSubmitting] = useState(false);
  const [offlineSuccess, setOfflineSuccess] = useState<string | null>(null);

  useEffect(() => {
    apiClient('/dashboard/extension-offer')
      .then((data) => setOffer(data as ExtensionOffer))
      .catch((e) => setError(e?.message || 'Failed to load extension offer'))
      .finally(() => setOfferLoading(false));
  }, []);

  const isForeign = offer?.currency_name === 'USD';
  const displayAmount = offer?.estimated_amount ?? 0;
  const paymentAmountINR = offer?.payment_amount_inr ?? displayAmount;

  const reportPaymentFailed = async (requestId: string, reason?: string) => {
    try {
      await apiClient('/registration/extension/report-failed', {
        method: 'POST',
        body: JSON.stringify({ request_id: requestId, reason: reason || undefined }),
      });
      setShowOfflineForm(true);
    } catch {
      setShowOfflineForm(true);
    }
  };

  const handleOfflineSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeRequestId || !offlineReference.trim()) return;
    setOfflineSubmitting(true);
    setError(null);
    try {
      const res = (await apiClient('/registration/extension/report-offline', {
        method: 'POST',
        body: JSON.stringify({
          request_id: activeRequestId,
          offline_reference: offlineReference.trim(),
          note: offlineNote.trim() || undefined,
        }),
      })) as { message?: string };
      setOfflineSuccess(res?.message || 'Submitted for admin review.');
      setShowOfflineForm(false);
    } catch (err: unknown) {
      const msg =
        (err as { detail?: string; message?: string })?.detail ||
        (err as { message?: string })?.message ||
        'Could not submit offline payment details.';
      setError(msg);
    } finally {
      setOfflineSubmitting(false);
    }
  };

  const handleExtend = async () => {
    setLoading(true);
    setError(null);
    setOfflineSuccess(null);
    setShowOfflineForm(false);
    try {
      const init = await apiClient('/registration/extension/init', {
        method: 'POST',
      });
      const requestId = init.request_id as string;
      setActiveRequestId(requestId);
      const order = await apiClient('/registration/payment/order', {
        method: 'POST',
        body: JSON.stringify({ request_id: requestId }),
      });

      const script = document.createElement('script');
      script.src = 'https://checkout.razorpay.com/v1/checkout.js';
      script.async = true;
      script.onload = () => {
        if (!order.key_id || !order.order_id) {
          setError('Payment cannot start due to missing Razorpay order details.');
          setLoading(false);
          return;
        }
        const options = {
          key: order.key_id,
          amount: Math.round(order.amount * 100),
          currency: order.currency,
          name: 'Dr. Harish CCM',
          description: `Subscription Extension (${offer?.extension_months || 2} months)`,
          order_id: order.order_id,
          handler: async (response: {
            razorpay_order_id: string;
            razorpay_payment_id: string;
            razorpay_signature: string;
          }) => {
            const paymentPayload = {
              request_id: requestId,
              order_id: response.razorpay_order_id,
              payment_id: response.razorpay_payment_id,
              signature: response.razorpay_signature,
              raw_payload: response,
            };
            try {
              const confirmed = (await apiClient('/registration/extension/confirm', {
                method: 'POST',
                body: JSON.stringify(paymentPayload),
              })) as { message?: string; extended_end_at?: string };
              const until = confirmed?.extended_end_at
                ? formatDisplayDate(confirmed.extended_end_at)
                : null;
              alert(
                until
                  ? `Payment successful. Your access is extended until ${until}.`
                  : confirmed?.message || 'Payment successful. Your access has been extended.',
              );
              navigate('/dashboard');
            } catch (e: unknown) {
              try {
                await apiClient('/registration/extension/confirm', { method: 'POST', body: '{}' });
                alert('Payment captured. Your access has been extended.');
                navigate('/dashboard');
              } catch (syncErr: unknown) {
                const msg =
                  (syncErr as { detail?: string; message?: string })?.detail ||
                  (syncErr as { message?: string })?.message ||
                  (e as { message?: string })?.message ||
                  'Payment verification failed. Please refresh dashboard in a minute.';
                setError(msg);
              }
            } finally {
              setLoading(false);
            }
          },
          modal: {
            ondismiss: () => {
              void reportPaymentFailed(requestId, 'Checkout closed without payment');
              setError('Payment was not completed. You can submit offline payment details below.');
              setLoading(false);
            },
          },
          prefill: {
            name: user?.name || '',
            email: user?.email || '',
          },
          theme: { color: '#00C897' },
        };
        const rzp = new (window as any).Razorpay(options);
        rzp.on('payment.failed', (resp: { error?: { description?: string; reason?: string } }) => {
          const desc = resp?.error?.description || resp?.error?.reason || 'Payment failed';
          void reportPaymentFailed(requestId, desc);
          setError(`Payment was not completed: ${desc}`);
          setLoading(false);
        });
        rzp.open();
      };
      document.body.appendChild(script);
    } catch (e: unknown) {
      setError((e as { message?: string })?.message || 'Failed to initiate extension payment.');
      setLoading(false);
    }
  };

  if (offerLoading) {
    return <div className="p-8 text-center font-mono text-xs text-ink-muted">Loading extension details…</div>;
  }

  if (!offer?.enabled) {
    return (
      <div className="p-6 lg:p-8 max-w-2xl">
        <h1 className="font-display font-bold text-3xl text-slate mb-3">Extend Subscription</h1>
        <p className="font-sans text-sm text-ink-muted">{offer?.reason || 'Extension is not available at this time.'}</p>
        <Link to="/dashboard" className="inline-block mt-6 font-sans text-sm text-mint hover:underline">← Back to Dashboard</Link>
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8 max-w-2xl">
      <h1 className="font-display font-bold text-3xl text-slate mb-3">Extend Subscription</h1>
      {offer.headline ? (
        <p className="font-sans text-sm text-ink-secondary mb-3 leading-relaxed">{offer.headline}</p>
      ) : (
        <p className="font-sans text-sm text-ink-muted mb-3">
          Extend your current subscription by <strong>{offer.extension_months} months</strong>.
        </p>
      )}
      {(offer.batch_end_date || offer.extended_end_date) && (
        <p className="font-sans text-sm text-ink-muted mb-6">
          You can pay now. Extended access runs from{' '}
          <strong>{formatDisplayDate(offer.batch_end_date)}</strong>
          {offer.extended_end_date ? (
            <>
              {' '}until <strong>{formatDisplayDate(offer.extended_end_date)}</strong>
            </>
          ) : null}
          .
        </p>
      )}
      {!offer.batch_end_date && !offer.extended_end_date && (
        <p className="font-sans text-sm text-ink-muted mb-6">
          Payment is available now. Your access will be extended by {offer.extension_months} months from the official batch end date.
        </p>
      )}

      <div className="bg-chalk border border-border-soft rounded-sm p-5 mb-6 space-y-3 shadow-sm">
        <h3 className="font-mono text-[10px] text-ink-faint uppercase tracking-wider">Pricing Summary</h3>

        {offer.gross_amount != null && offer.gst_percentage != null && (
          <div className="space-y-2 text-sm font-sans">
            <div className="flex justify-between">
              <span className="text-ink-muted">Gross Amount</span>
              <span className="font-mono text-slate">₹{offer.gross_amount?.toLocaleString()}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-ink-muted">GST ({offer.gst_percentage}%)</span>
              <span className="font-mono text-slate">₹{offer.gst_amount?.toLocaleString()}</span>
            </div>
            <div className="border-t border-border-soft pt-2 flex justify-between font-bold">
              <span className="text-slate">Total (INR)</span>
              <span className="font-mono text-slate text-lg">₹{paymentAmountINR.toLocaleString()}</span>
            </div>
          </div>
        )}

        {isForeign && (
          <div className="mt-3 p-3 bg-blue-50 border border-blue-100 rounded-sm">
            <div className="flex justify-between items-center">
              <span className="text-sm text-blue-800 font-medium">Equivalent in USD</span>
              <span className="font-mono text-blue-900 font-bold text-lg">${displayAmount}</span>
            </div>
            <p className="text-[11px] text-blue-600 mt-1 italic">
              Payment will be processed in Indian Rupees (₹{paymentAmountINR.toLocaleString()}) via Razorpay.
            </p>
          </div>
        )}

        {!isForeign && !offer.gross_amount && (
          <div className="flex justify-between text-sm font-bold">
            <span className="text-slate">Amount Payable</span>
            <span className="font-mono text-slate text-lg">₹{paymentAmountINR.toLocaleString()}</span>
          </div>
        )}

        <div className="flex justify-between text-xs text-ink-faint pt-1">
          <span>Duration</span>
          <span className="font-mono">{offer.extension_months} Months</span>
        </div>
      </div>

      {error && <div className="mb-4 text-sm text-red-600 bg-red-50 border border-red-100 rounded-sm px-4 py-3">{error}</div>}
      {offlineSuccess && (
        <div className="mb-4 text-sm text-mint bg-mint/10 border border-mint/20 rounded-sm px-4 py-3">{offlineSuccess}</div>
      )}

      <div className="flex items-center gap-3 mb-6">
        <button
          type="button"
          onClick={() => void handleExtend()}
          disabled={loading || offlineSubmitting}
          className="magnetic bg-slate text-chalk rounded-sm px-6 py-3 font-sans font-semibold text-sm hover:bg-slate-light disabled:opacity-50"
        >
          {loading ? 'Processing…' : `Pay ₹${paymentAmountINR.toLocaleString()} & Extend`}
        </button>
        <Link to="/dashboard" className="font-sans text-sm text-ink-muted hover:text-ink">
          Cancel
        </Link>
      </div>

      {showOfflineForm && !offlineSuccess && (
        <div className="bg-chalk-warm border border-border-soft rounded-sm p-5 space-y-4">
          <div>
            <h2 className="font-sans font-semibold text-slate text-sm">Paid offline instead?</h2>
            <p className="font-sans text-xs text-ink-muted mt-1">
              If your online payment failed but you transferred the amount via bank/UPI, submit your transaction reference for admin approval.
            </p>
          </div>
          <form className="space-y-3" onSubmit={(e) => void handleOfflineSubmit(e)}>
            <div>
              <label className="block font-mono text-[10px] text-ink-faint uppercase tracking-wider mb-1">
                Transaction reference / UTR
              </label>
              <input
                type="text"
                required
                value={offlineReference}
                onChange={(e) => setOfflineReference(e.target.value)}
                className="w-full bg-chalk border border-border-soft rounded-sm py-2 px-3 text-sm outline-none focus:border-mint/50"
                placeholder="e.g. UTR or bank reference number"
              />
            </div>
            <div>
              <label className="block font-mono text-[10px] text-ink-faint uppercase tracking-wider mb-1">
                Note (optional)
              </label>
              <textarea
                value={offlineNote}
                onChange={(e) => setOfflineNote(e.target.value)}
                rows={2}
                className="w-full bg-chalk border border-border-soft rounded-sm py-2 px-3 text-sm outline-none focus:border-mint/50 resize-none"
                placeholder="Payment date, bank name, or other details"
              />
            </div>
            <button
              type="submit"
              disabled={offlineSubmitting || !activeRequestId || !offlineReference.trim()}
              className="bg-mint text-slate rounded-sm px-5 py-2 font-sans text-sm font-semibold disabled:opacity-50"
            >
              {offlineSubmitting ? 'Submitting…' : 'Submit for admin review'}
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
