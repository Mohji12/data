import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';
import Navbar from '@/components/Navbar';
import Footer from '@/components/Footer';
import { apiClient } from '@/lib/apiClient';
import { resolvePublicUploadUrl } from '@/lib/apiBase';
import { EVENT_DISPLAY_NAME, EVENT_SLUG } from '@/lib/eventConclave';
import { FileText } from 'lucide-react';

const API_BASE = `/events/${EVENT_SLUG}`;

type Category = 'clinician' | 'student';

type FeeCell = {
  base_fee_inr: number;
  gst_percent: number;
  gst_amount_inr: number;
  total_fee_inr: number;
};

type EventConfig = {
  active: boolean;
  registration_open: boolean;
  current_tier: string | null;
  current_tier_label: string | null;
  fee_schedule: Record<string, Record<string, FeeCell>>;
  contact_phone?: string;
  contact_name?: string;
  brochure_url?: string | null;
};

type PayableResponse = FeeCell & {
  tier?: string;
  tier_label?: string;
  category?: string;
  fee_inr?: number;
};

const TIER_ORDER = ['early_bird', 'regular', 'spot'] as const;

const TIER_HEADINGS: Record<(typeof TIER_ORDER)[number], string> = {
  early_bird: 'Early Bird (up to 8 Jul 2026)',
  regular: 'Regular (9–10 Jul 2026)',
  spot: 'Spot (11–12 Jul 2026)',
};

const inputClass =
  'w-full bg-chalk border border-border-soft rounded-sm py-3 px-4 font-sans text-sm text-ink focus:border-mint/50 focus:ring-1 focus:ring-mint/15 outline-none';

function formatInr(n: number) {
  return n.toLocaleString('en-IN', { minimumFractionDigits: 0, maximumFractionDigits: 2 });
}

export default function EventConclaveRegister() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    full_name: '',
    designation: '',
    category: 'clinician' as Category,
    specialty: '',
    email: '',
    phone: '',
    country_id: '',
    country_name: '',
    hospital: '',
    city: '',
    state: '',
    council_state: '',
    council_registration_number: '',
    declaration_accepted: false,
  });

  const { data: config, isLoading: configLoading, isError: configError } = useQuery({
    queryKey: ['event-config', EVENT_SLUG],
    queryFn: () => apiClient(`${API_BASE}/config`) as Promise<EventConfig>,
  });

  const { data: payable, isLoading: payableLoading } = useQuery({
    queryKey: ['event-payable', EVENT_SLUG, form.category],
    queryFn: () =>
      apiClient(`${API_BASE}/payable`, {
        method: 'POST',
        body: JSON.stringify({ category: form.category }),
      }) as Promise<PayableResponse>,
    enabled: !!config?.registration_open,
  });

  const { data: countries = [] } = useQuery({
    queryKey: ['registration-countries'],
    queryFn: () => apiClient('/registration/countries'),
  });

  const update = (key: string, value: string | boolean) => {
    setForm((f) => ({ ...f, [key]: value }));
  };

  const onCountryChange = (countryId: string) => {
    const c = countries.find((x: { id: number }) => String(x.id) === countryId);
    setForm((f) => ({
      ...f,
      country_id: countryId,
      country_name: c?.name || '',
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.declaration_accepted) {
      toast.error('Please accept the declaration to continue.');
      return;
    }
    setLoading(true);
    try {
      const resInit = await apiClient(`${API_BASE}/init`, {
        method: 'POST',
        body: JSON.stringify({
          ...form,
          country_id: parseInt(form.country_id, 10),
          declaration_accepted: true,
        }),
      });

      if (resInit.payment_required === false) {
        navigate(
          `/events/${EVENT_SLUG}/thank-you?reg=${encodeURIComponent(resInit.registration_number)}&id=${resInit.registration_id}`,
        );
        return;
      }

      const requestId = resInit.request_id;
      const order = await apiClient(`${API_BASE}/payment/order`, {
        method: 'POST',
        body: JSON.stringify({ request_id: requestId }),
      });

      const script = document.createElement('script');
      script.src = 'https://checkout.razorpay.com/v1/checkout.js';
      script.async = true;
      script.onload = () => {
        if (!order.key_id || !order.order_id) {
          toast.error('Payment could not start. Check Razorpay configuration on the server.');
          setLoading(false);
          return;
        }
        const options = {
          key: order.key_id,
          amount: Math.round(order.amount * 100),
          currency: order.currency,
          name: 'Dr. Harish CCM',
          description: `${EVENT_DISPLAY_NAME} Registration`,
          order_id: order.order_id,
          handler: async (response: {
            razorpay_order_id: string;
            razorpay_payment_id: string;
            razorpay_signature: string;
          }) => {
            setLoading(true);
            try {
              await apiClient(`${API_BASE}/payment/callback`, {
                method: 'POST',
                body: JSON.stringify({
                  request_id: requestId,
                  order_id: response.razorpay_order_id,
                  payment_id: response.razorpay_payment_id,
                  signature: response.razorpay_signature,
                  raw_payload: response,
                }),
              });
              navigate(
                `/events/${EVENT_SLUG}/thank-you?reg=${encodeURIComponent(resInit.registration_number)}&id=${resInit.registration_id}`,
              );
            } catch (err: unknown) {
              toast.error(err instanceof Error ? err.message : 'Payment verification failed.');
            } finally {
              setLoading(false);
            }
          },
          modal: {
            ondismiss: () => setLoading(false),
          },
          prefill: {
            name: form.full_name,
            email: form.email,
            contact: form.phone,
          },
          theme: { color: '#00C897' },
        };
        const rzp = new (window as Window & { Razorpay?: new (o: object) => { open: () => void; on: (e: string, h: (r: unknown) => void) => void } }).Razorpay!(
          options,
        );
        rzp.on('payment.failed', (resp: { error?: { description?: string; reason?: string } }) => {
          const desc = resp?.error?.description || resp?.error?.reason || 'Payment failed';
          toast.error(`Payment was not completed: ${desc}`);
          setLoading(false);
        });
        rzp.open();
      };
      document.body.appendChild(script);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : 'Registration failed.');
      setLoading(false);
    }
  };

  if (configLoading) {
    return (
      <div className="min-h-screen bg-chalk-warm flex items-center justify-center font-sans text-ink-muted">
        Loading…
      </div>
    );
  }

  if (configError || !config) {
    return (
      <div className="min-h-screen bg-chalk-warm">
        <Navbar />
        <div className="max-w-lg mx-auto px-4 py-24 text-center">
          <h1 className="font-display font-bold text-3xl text-slate mb-4">Unable to load registration fee</h1>
          <p className="font-sans text-ink-muted mb-8">
            Could not load event pricing from the server. Ensure the backend API is running and refresh the page.
          </p>
          <Link to="/" className="text-mint hover:text-mint-dark font-sans">
            ← Back to home
          </Link>
        </div>
        <Footer />
      </div>
    );
  }

  if (!config.registration_open || config.active === false) {
    return (
      <div className="min-h-screen bg-chalk-warm">
        <Navbar />
        <div className="max-w-lg mx-auto px-4 py-24 text-center">
          <h1 className="font-display font-bold text-3xl text-slate mb-4">Registration closed</h1>
          <p className="font-sans text-ink-muted mb-8">{EVENT_DISPLAY_NAME} registration is not open at this time.</p>
          <Link to="/" className="text-mint hover:text-mint-dark font-sans">
            ← Back to home
          </Link>
        </div>
        <Footer />
      </div>
    );
  }

  const baseFee = payable?.base_fee_inr ?? 0;
  const gstPercent = payable?.gst_percent ?? 18;
  const gstAmount = payable?.gst_amount_inr ?? 0;
  const totalFee = payable?.total_fee_inr ?? payable?.fee_inr ?? 0;
  const currentTier = config.current_tier;
  const brochureUrl = resolvePublicUploadUrl(config.brochure_url);

  return (
    <div className="min-h-screen bg-chalk-warm">
      <Navbar />
      <div className="max-w-3xl mx-auto px-4 py-12 lg:py-16">
        <Link to="/" className="font-mono text-[10px] text-mint tracking-[0.2em] uppercase mb-6 block">
          ← Home
        </Link>

        <header className="mb-10 border-b border-border-soft pb-8">
          <p className="font-mono text-[10px] text-mint tracking-[0.2em] uppercase mb-2">Registration form</p>
          <h1 className="font-display font-extrabold text-3xl lg:text-4xl text-slate leading-tight">
            <span className="block">1st NATIONAL &ldquo;ICU-ID CONCLAVE&rdquo;</span>
            <span className="block mt-2">KMC CREDIT HOURS AVAILABLE</span>
          </h1>
          <p className="font-sans text-lg text-ink-secondary mt-2">11th and 12th July 2026</p>
          {config.current_tier_label && (
            <p className="font-mono text-[11px] text-mint mt-3 uppercase tracking-wide">
              Current fee window: {config.current_tier_label}
            </p>
          )}
        </header>

        {brochureUrl && (
          <section className="mb-10 bg-chalk border border-border-soft rounded-sm p-6 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-4">
              <div>
                <h2 className="font-display font-bold text-lg text-slate flex items-center gap-2">
                  <FileText size={18} className="text-mint shrink-0" />
                  Conference brochure
                </h2>
                <p className="font-sans text-sm text-ink-muted mt-1">
                  Download or view the PDF for programme details, faculty, and venue information.
                </p>
              </div>
              <a
                href={brochureUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center rounded-sm bg-slate text-chalk px-5 py-2.5 font-sans text-sm font-semibold hover:bg-slate-light transition-colors shrink-0"
              >
                Open brochure PDF
              </a>
            </div>
            <div className="w-full h-[min(70vh,560px)] overflow-hidden rounded-sm border border-border-soft bg-chalk-warm">
              <iframe src={brochureUrl} title="ICU-ID Conclave brochure" className="w-full h-full border-0" />
            </div>
          </section>
        )}

        <form onSubmit={handleSubmit} className="space-y-10">
          <section className="bg-chalk border border-border-soft rounded-sm p-6 overflow-x-auto">
            <h2 className="font-display font-bold text-lg text-slate mb-4">Registration fee structure</h2>
            <table className="w-full font-sans text-sm text-left min-w-[520px]">
              <thead>
                <tr className="border-b border-border-soft text-[11px] uppercase tracking-wide text-ink-faint">
                  <th className="py-2 pr-3">Period</th>
                  <th className="py-2 pr-3">Student (incl. 18% GST)</th>
                  <th className="py-2">Practicing Clinician (incl. 18% GST)</th>
                </tr>
              </thead>
              <tbody>
                {TIER_ORDER.map((tier) => {
                  const row = config.fee_schedule?.[tier];
                  const student = row?.student;
                  const clinician = row?.clinician;
                  const active = tier === currentTier;
                  return (
                    <tr
                      key={tier}
                      className={`border-b border-border-soft ${active ? 'bg-mint-pale/60' : ''}`}
                    >
                      <td className="py-3 pr-3 align-top">
                        <span className="font-medium text-slate">{TIER_HEADINGS[tier]}</span>
                        {active && (
                          <span className="ml-2 inline-block text-[10px] font-mono uppercase tracking-wide text-mint">
                            Active now
                          </span>
                        )}
                      </td>
                      <td className="py-3 pr-3 text-ink-secondary">
                        {student ? (
                          <>
                            ₹ {formatInr(student.base_fee_inr)} + ₹ {formatInr(student.gst_amount_inr)} GST
                            <br />
                            <span className="font-semibold text-slate">₹ {formatInr(student.total_fee_inr)}</span>
                          </>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td className="py-3 text-ink-secondary">
                        {clinician ? (
                          <>
                            ₹ {formatInr(clinician.base_fee_inr)} + ₹ {formatInr(clinician.gst_amount_inr)} GST
                            <br />
                            <span className="font-semibold text-slate">₹ {formatInr(clinician.total_fee_inr)}</span>
                          </>
                        ) : (
                          '—'
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p className="font-sans text-xs text-ink-muted mt-4">
              Student: valid student ID or proof must be furnished on the day of the conference.
            </p>
          </section>

          <section>
            <h2 className="font-display font-bold text-xl text-slate mb-6">Personal details</h2>
            <div className="space-y-4">
              <Field label="1. Full name *">
                <input className={inputClass} value={form.full_name} onChange={(e) => update('full_name', e.target.value)} required />
              </Field>
              <Field label="2. Designation *">
                <input className={inputClass} value={form.designation} onChange={(e) => update('designation', e.target.value)} required />
              </Field>
              <Field label="3. Category *">
                <div className="flex flex-wrap gap-6 font-sans text-sm">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="category"
                      checked={form.category === 'clinician'}
                      onChange={() => update('category', 'clinician')}
                    />
                    Practicing Clinician
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="category"
                      checked={form.category === 'student'}
                      onChange={() => update('category', 'student')}
                    />
                    Student
                  </label>
                </div>
                <p className="font-sans text-xs text-ink-muted mt-2">
                  Students must bring valid student ID or proof on the conference day.
                </p>
              </Field>
              <Field label="4. Specialty *">
                <input className={inputClass} value={form.specialty} onChange={(e) => update('specialty', e.target.value)} required />
              </Field>
              <Field label="5. Email ID *">
                <input type="email" className={inputClass} value={form.email} onChange={(e) => update('email', e.target.value)} required />
              </Field>
              <Field label="6. Phone number (WhatsApp preferred) *">
                <input type="tel" className={inputClass} value={form.phone} onChange={(e) => update('phone', e.target.value)} required />
              </Field>
              <Field label="7. Country *">
                <select
                  className={inputClass}
                  value={form.country_id}
                  onChange={(e) => onCountryChange(e.target.value)}
                  required
                >
                  <option value="">Select country</option>
                  {countries.map((c: { id: number; name: string }) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="8. Hospital / Institution name *">
                <input className={inputClass} value={form.hospital} onChange={(e) => update('hospital', e.target.value)} required />
              </Field>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Field label="9. City *">
                  <input className={inputClass} value={form.city} onChange={(e) => update('city', e.target.value)} required />
                </Field>
                <Field label="10. State *">
                  <input className={inputClass} value={form.state} onChange={(e) => update('state', e.target.value)} required />
                </Field>
              </div>
            </div>
          </section>

          <section>
            <h2 className="font-display font-bold text-xl text-slate mb-6">Medical or nursing council details</h2>
            <div className="space-y-4">
              <Field label="11. State in which registration done *">
                <input className={inputClass} value={form.council_state} onChange={(e) => update('council_state', e.target.value)} required />
              </Field>
              <Field label="12. Medical / Nursing council registration number *">
                <input
                  className={inputClass}
                  value={form.council_registration_number}
                  onChange={(e) => update('council_registration_number', e.target.value)}
                  required
                />
              </Field>
            </div>
          </section>

          <section className="bg-chalk border border-border-soft rounded-sm p-6">
            <h2 className="font-display font-bold text-lg text-slate mb-2">Your registration fee</h2>
            {payable?.tier_label && (
              <p className="font-sans text-xs text-ink-muted mb-3">{payable.tier_label}</p>
            )}
            {payableLoading ? (
              <p className="font-sans text-sm text-ink-muted mb-4">Calculating fee…</p>
            ) : (
              <div className="font-sans text-sm text-ink-secondary space-y-2 mb-4">
                <div className="flex justify-between">
                  <span>Base fee ({form.category === 'student' ? 'Student' : 'Practicing Clinician'})</span>
                  <span>₹ {formatInr(baseFee)}</span>
                </div>
                <div className="flex justify-between">
                  <span>GST ({gstPercent}%)</span>
                  <span>₹ {formatInr(gstAmount)}</span>
                </div>
                <div className="flex justify-between border-t border-border-soft pt-2 font-semibold text-slate">
                  <span>Total payable</span>
                  <span className="font-display font-black text-xl text-mint">
                    ₹ {formatInr(totalFee)}{' '}
                    <span className="font-sans text-sm font-normal text-ink-muted">INR</span>
                  </span>
                </div>
              </div>
            )}
            <p className="font-sans text-sm text-ink-muted mb-6">
              Click Register now to pay securely via Razorpay. Your unique registration number will be emailed after
              successful payment.
            </p>
            <button
              type="submit"
              disabled={loading || payableLoading || totalFee <= 0}
              className="magnetic w-full bg-slate text-chalk rounded-sm py-4 font-sans font-semibold hover:bg-slate-light transition-all disabled:opacity-50"
            >
              {loading ? 'Processing…' : 'Register now — Pay with Razorpay'}
            </button>
          </section>

          <section className="border border-border-soft rounded-sm p-6 bg-chalk/50">
            <h2 className="font-display font-bold text-lg text-slate mb-4">Declaration</h2>
            <label className="flex items-start gap-3 font-sans text-sm text-ink cursor-pointer">
              <input
                type="checkbox"
                className="mt-1"
                checked={form.declaration_accepted}
                onChange={(e) => update('declaration_accepted', e.target.checked)}
              />
              <span>I confirm that the above details provided are correct and authentic.</span>
            </label>
          </section>

          <section className="font-sans text-sm text-ink-secondary border-t border-border-soft pt-8">
            <h2 className="font-display font-bold text-slate mb-2">Contact details</h2>
            <p>For any queries, please contact:</p>
            <p className="font-semibold text-slate mt-2">{config?.contact_name || 'Dr. Harish Mallapura Maheshwarappa'}</p>
            <p className="text-mint font-medium">{config?.contact_phone || '+91 8095218493'}</p>
          </section>
        </form>
      </div>
      <Footer />
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="font-mono text-[10px] text-ink-faint uppercase tracking-[0.12em] mb-1.5 block">{label}</label>
      {children}
    </div>
  );
}
