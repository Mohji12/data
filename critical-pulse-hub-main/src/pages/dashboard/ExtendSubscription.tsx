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

  useEffect(() => {
    apiClient('/dashboard/extension-offer')
      .then((data) => setOffer(data as ExtensionOffer))
      .catch((e) => setError(e?.message || 'Failed to load extension offer'))
      .finally(() => setOfferLoading(false));
  }, []);

  const isForeign = offer?.currency_name === 'USD';
  const displayAmount = offer?.estimated_amount ?? 0;
  const displayCurrency = offer?.currency_name || 'INR';
  const paymentAmountINR = offer?.payment_amount_inr ?? displayAmount;

  const handleExtend = async () => {
    setLoading(true);
    setError(null);
    try {
      const init = await apiClient('/registration/extension/init', {
        method: 'POST',
      });
      const requestId = init.request_id as string;
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
            ondismiss: () => setLoading(false),
          },
          prefill: {
            name: user?.name || '',
            email: user?.email || '',
          },
          theme: { color: '#00C897' },
        };
        const rzp = new (window as any).Razorpay(options);
        rzp.on('payment.failed', (resp: any) => {
          const desc = resp?.error?.description || resp?.error?.reason || 'Payment failed';
          setError(`Payment was not completed: ${desc}`);
          setLoading(false);
        });
        rzp.open();
      };
      document.body.appendChild(script);
    } catch (e: any) {
      setError(e?.message || 'Failed to initiate extension payment.');
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

      {/* Pricing Card */}
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

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => void handleExtend()}
          disabled={loading}
          className="magnetic bg-slate text-chalk rounded-sm px-6 py-3 font-sans font-semibold text-sm hover:bg-slate-light disabled:opacity-50"
        >
          {loading ? 'Processing…' : `Pay ₹${paymentAmountINR.toLocaleString()} & Extend`}
        </button>
        <Link to="/dashboard" className="font-sans text-sm text-ink-muted hover:text-ink">
          Cancel
        </Link>
      </div>
    </div>
  );
}
