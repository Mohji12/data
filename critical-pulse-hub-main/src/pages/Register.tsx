import { useState, useEffect, useMemo } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Check, ChevronRight, Sparkles } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/apiClient';
import { pickRegistrationBatches } from '@/lib/mockData';

const steps = ['Personal', 'Professional', 'Course & Payment'];

const publicAsset = (path: string) => {
  const base = import.meta.env.BASE_URL || '/';
  return `${base.endsWith('/') ? base : `${base}/`}${path.replace(/^\//, '')}`;
};

/** Full-page background in `public/hero/` */
const REGISTER_BG_IMAGE = publicAsset('hero/register-bg.jpg');
const REGISTER_BG_FALLBACK = publicAsset('hero/A_3D_medical_202604071049.png');

export default function Register() {
  const [searchParams] = useSearchParams();
  const [step, setStep] = useState(0);
  const [form, setForm] = useState<Record<string, any>>({ 
    batch_slug: '', 
    package_id: '',
    country_id: 101, // Default to India/101
    registration_type: 'Indian Delegates',
    title: '',
    name: '',
    email: '',
    password: '',
    retype_password: '',
    phone: '',
    state: '',
    city: '',
    pin_code: '',
    hospital: '',
    qualification: '',
    speciality: '',
    coupon_code: '',
    document_file: '',
  });
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const { data: countries } = useQuery({
    queryKey: ['regCountries'],
    queryFn: () => apiClient('/registration/countries')
  });

  const { data: batches } = useQuery({
    queryKey: ['regBatches'],
    queryFn: () => apiClient('/registration/batches')
  });

  useEffect(() => {
    const batch = searchParams.get('batch')?.trim();
    const packageId = searchParams.get('package_id')?.trim();
    const countryParam = searchParams.get('country_id')?.trim();
    const foreign = searchParams.get('foreign')?.trim() === '1';

    if (countryParam && /^\d+$/.test(countryParam)) {
      setForm((f) => ({ ...f, country_id: Number(countryParam) }));
    } else if (foreign && countries?.length) {
      const foreignCountry = countries.find((c: any) => String(c.id) !== '101');
      if (foreignCountry) {
        setForm((f) => ({
          ...f,
          country_id: Number(foreignCountry.id),
          registration_type: 'Foreign Delegates',
        }));
      }
    }

    if (batch) {
      setForm((f) => (f.batch_slug === batch ? f : { ...f, batch_slug: batch }));
    }
    if (packageId) {
      setForm((f) => ({ ...f, package_id: packageId }));
    }
  }, [searchParams, countries]);

  const chooseCourseBatches = useMemo(() => {
    const picked = pickRegistrationBatches(batches);
    const slugs = new Set(picked.map((b) => b.slug));
    const extraSlug = form.batch_slug?.trim();
    if (extraSlug && batches && !slugs.has(extraSlug)) {
      const row = (batches as any[]).find((b) => b.slug === extraSlug);
      if (row) {
        return [...picked, { ...row, displayTitle: row.title }];
      }
    }
    return picked;
  }, [batches, form.batch_slug]);

  const selectedSubscription = useMemo(
    () => batches?.find((b: any) => b.slug === form.batch_slug)?.title || '',
    [batches, form.batch_slug],
  );
  const foreignOfferText = searchParams.get('foreign')?.trim() === '1'
    ? (searchParams.get('offer')?.trim() || '')
    : '';

  const { data: packages, isLoading: pkgsLoading } = useQuery({
    queryKey: ['regPackages', form.batch_slug, form.country_id, form.package_id],
    enabled: !!form.batch_slug,
    queryFn: () => {
      const p = new URLSearchParams();
      p.set('batch_slug', String(form.batch_slug || ''));
      p.set('country_id', String(form.country_id || ''));
      if (String(form.package_id || '').trim()) {
        p.set('selected_package_id', String(form.package_id).trim());
      }
      return apiClient(`/registration/packages?${p.toString()}`);
    }
  });

  const { data: payablePreview } = useQuery({
    queryKey: ['regPayablePreview', form.batch_slug, form.package_id, form.country_id, form.email, selectedSubscription],
    enabled: step === 2 && !!form.batch_slug && !!form.package_id && !!selectedSubscription,
    queryFn: () =>
      apiClient('/registration/payable-amount', {
        method: 'POST',
        body: JSON.stringify({
          batch_slug: form.batch_slug,
          package_id: parseInt(String(form.package_id), 10),
          country_id: parseInt(String(form.country_id), 10),
          subscription: selectedSubscription,
          email: String(form.email || '').trim().toLowerCase(),
        }),
      }),
  });

  const update = (k: string, v: any) => setForm({ ...form, [k]: v });
  const formatDurationLabel = (months?: number | null) => {
    if (!months) return '';
    if (months === 12) return '1 Year';
    return `${months} Months`;
  };
  const isPaymentStep = step === 2;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (step < 2) { 
        if (step === 0) {
            if (!form.title || !form.name || !form.email || !form.password || !form.phone || !form.registration_type) {
                alert("Please fill in all identity fields");
                return;
            }
            if (form.password.length !== 8) {
                alert("Password must be exactly 8 characters");
                return;
            }
            if (form.password !== form.retype_password) {
                alert("Passwords do not match");
                return;
            }
            if (form.registration_type === 'Indian Delegates' && form.phone.length !== 10) {
                alert("Please enter a valid 10-digit mobile number");
                return;
            }
        }
        if (step === 1) {
            if (!form.batch_slug || !form.hospital || !form.state || !form.city || !form.pin_code) {
                alert("Please enter all required professional and address details");
                return;
            }
            const sel = batches?.find((b: any) => b.slug === form.batch_slug);
            if (sel?.requires_document && !form.document_file) {
                alert("Please upload the required document");
                return;
            }
        }
        setStep(step + 1); 
        return; 
    }
    
    setLoading(true);
    let resInit;
    try {
      resInit = await apiClient('/registration/init', {
          method: 'POST',
          body: JSON.stringify({
              ...form,
              subscription: selectedSubscription,
              contact_number: form.phone,
              package_id: parseInt(form.package_id),
              country_id: parseInt(form.country_id),
          })
      });
    } catch (err: any) {
      alert(err.detail || err.message || "Registration failed");
      setLoading(false);
      return;
    }

    try {
      const requestId = resInit.request_id;
      const order = await apiClient('/registration/payment/order', {
          method: 'POST',
          body: JSON.stringify({ request_id: requestId })
      });

      const script = document.createElement('script');
      script.src = 'https://checkout.razorpay.com/v1/checkout.js';
      script.async = true;
      script.onload = () => {
          if (!order.key_id || !order.order_id) {
            alert(
              'Payment could not start: missing Razorpay key or order id. Configure PAYMENT_KEY_ID / PAYMENT_KEY_SECRET on the API server.',
            );
            setLoading(false);
            return;
          }
          const options = {
              key: order.key_id,
              amount: Math.round(order.amount * 100),
              currency: order.currency,
              name: 'Dr. Harish CCM',
              description: `Enrolment for ${form.batch_slug}`,
              order_id: order.order_id,
              handler: async (response: any) => {
                  setLoading(true);
                  try {
                      await apiClient('/registration/payment/callback', {
                          method: 'POST',
                          body: JSON.stringify({
                              request_id: requestId,
                              order_id: response.razorpay_order_id,
                              payment_id: response.razorpay_payment_id,
                              signature: response.razorpay_signature,
                              raw_payload: response
                          })
                      });
                      navigate(`/thank-you?reg=${resInit.registration_id}`);
                  } catch (err: any) {
                      alert(err.message || 'Payment verification failed.');
                  } finally {
                      setLoading(false);
                  }
              },
              modal: {
                ondismiss: () => {
                  setLoading(false);
                },
              },
              prefill: {
                  name: form.name,
                  email: form.email,
                  contact: form.phone
              },
              theme: { color: '#00C897' }
          };
          const rzp = new (window as any).Razorpay(options);
          rzp.on('payment.failed', (resp: any) => {
            const desc = resp?.error?.description || resp?.error?.reason || 'Payment failed';
            alert(`Payment was not completed: ${desc}`);
            setLoading(false);
          });
          rzp.open();
      };
      document.body.appendChild(script);
    } catch (err: any) {
      const msg = err?.message || 'Payment initiation failed';
      alert(
        msg.includes('Razorpay') || msg.includes('PAYMENT_KEY')
          ? msg
          : `${msg}\n\nTip: Razorpay needs real API keys in backend .env (PAYMENT_KEY_ID, PAYMENT_KEY_SECRET) and a server-created order — fake order ids always fail at checkout.`,
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative isolate min-h-screen flex items-center justify-center px-4 py-20 overflow-hidden">
      {/* Do not use negative z-index — it paints behind body bg-chalk and disappears. */}
      <img
        src={REGISTER_BG_IMAGE}
        alt=""
        aria-hidden
        className="pointer-events-none absolute inset-0 h-full w-full object-cover z-0"
        onError={(e) => {
          const img = e.currentTarget;
          if (img.dataset.fallback !== '1') {
            img.dataset.fallback = '1';
            img.src = REGISTER_BG_FALLBACK;
          }
        }}
      />
      <div
        className="pointer-events-none absolute inset-0 z-[1] bg-slate/35"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute inset-0 z-[1] bg-gradient-to-b from-chalk/50 via-chalk-warm/40 to-slate/50"
        aria-hidden
      />

      <div className="relative z-[2] w-full max-w-[680px] bg-chalk/92 border border-border-soft rounded-sm shadow-xl p-8 lg:p-12 backdrop-blur-sm">
        <Link to="/" className="font-mono text-xs text-mint tracking-[0.2em] uppercase mb-8 block">DR. HARISH CCM</Link>
        <h1 className="font-display font-extrabold text-4xl text-slate mb-2">Register</h1>
        <p className="font-sans text-sm text-ink-muted mb-10">Create your account in 3 simple steps.</p>

        {/* Step indicator */}
        <div className="flex items-center justify-center gap-0 mb-12">
          {steps.map((s, i) => (
            <div key={i} className="flex items-center">
              <div className="flex flex-col items-center">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-mono border-2 transition-all ${
                  i < step ? 'bg-mint text-slate border-mint' :
                  i === step ? 'bg-slate text-chalk border-slate' :
                  'border-border-strong text-ink-faint'
                }`}>
                  {i < step ? <Check size={14} /> : i + 1}
                </div>
                <span className="font-mono text-xs text-ink-faint mt-2">{s}</span>
              </div>
              {i < 2 && <div className={`w-12 lg:w-20 h-px mx-2 mt-[-20px] ${i < step ? 'bg-mint' : 'bg-border-soft'}`} />}
            </div>
          ))}
        </div>

        <form onSubmit={handleSubmit}>
          <AnimatePresence mode="wait">
            {step === 0 && (
              <motion.div key="s0" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
                  <div className="sm:col-span-1">
                    <label className="font-mono text-[10px] text-ink-faint uppercase tracking-[0.12em] mb-1.5 block">Title</label>
                    <select value={form.title || ''} onChange={(e) => update('title', e.target.value)} className="w-full bg-chalk border border-border-soft rounded-sm py-3 px-4 font-sans text-sm text-ink outline-none" required>
                      <option value="">Select</option>
                      <option value="Dr.">Dr</option>
                      <option value="Prof.">Prof</option>
                    </select>
                  </div>
                  <div className="sm:col-span-3">
                    <label className="font-mono text-[10px] text-ink-faint uppercase tracking-[0.12em] mb-1.5 block">Full Name</label>
                    <input value={form.name || ''} onChange={(e) => update('name', e.target.value)} className="w-full bg-chalk border border-border-soft rounded-sm py-3 px-4 font-sans text-sm text-ink focus:border-mint/50 focus:ring-1 focus:ring-mint/15 outline-none" required />
                  </div>
                </div>

                <div>
                   <label className="font-mono text-xs text-ink-faint uppercase tracking-[0.12em] mb-3 block">Registration Type</label>
                   <div className="flex gap-6">
                      <label className="flex items-center gap-2 cursor-pointer group">
                        <input type="radio" name="registration_type" value="Indian Delegates" checked={form.registration_type === 'Indian Delegates'} onChange={(e) => update('registration_type', e.target.value)} className="w-4 h-4 text-mint border-border-strong focus:ring-mint/20" />
                        <span className="font-sans text-sm text-slate group-hover:text-ink transition-colors">Indian Delegates</span>
                      </label>
                      <label className="flex items-center gap-2 cursor-pointer group">
                        <input type="radio" name="registration_type" value="Foreign Delegates" checked={form.registration_type === 'Foreign Delegates'} onChange={(e) => update('registration_type', e.target.value)} className="w-4 h-4 text-mint border-border-strong focus:ring-mint/20" />
                        <span className="font-sans text-sm text-slate group-hover:text-ink transition-colors">Foreign Delegates</span>
                      </label>
                   </div>
                </div>
                <div>
                  <label className="font-mono text-[10px] text-ink-faint uppercase tracking-[0.12em] mb-1.5 block">Email</label>
                  <input type="email" value={form.email || ''} onChange={(e) => update('email', e.target.value)} className="w-full bg-chalk border border-border-soft rounded-sm py-3 px-4 font-sans text-sm text-ink focus:border-mint/50 outline-none" required />
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="font-mono text-[10px] text-ink-faint uppercase tracking-[0.12em] mb-1.5 block">Password (Exact 8 chars)</label>
                    <input type="password" value={form.password || ''} maxLength={8} minLength={8} onChange={(e) => update('password', e.target.value)} className="w-full bg-chalk border border-border-soft rounded-sm py-3 px-4 font-sans text-sm text-ink focus:border-mint/50 outline-none" required />
                  </div>
                  <div>
                    <label className="font-mono text-[10px] text-ink-faint uppercase tracking-[0.12em] mb-1.5 block">Re-type Password</label>
                    <input type="password" value={form.retype_password || ''} onChange={(e) => update('retype_password', e.target.value)} className="w-full bg-chalk border border-border-soft rounded-sm py-3 px-4 font-sans text-sm text-ink focus:border-mint/50 outline-none" required />
                  </div>
                </div>
                <div>
                   <label className="font-mono text-[10px] text-ink-faint uppercase tracking-[0.12em] mb-1.5 block">Phone Number</label>
                   <input type="tel" value={form.phone || ''} onChange={(e) => update('phone', e.target.value)} className="w-full bg-chalk border border-border-soft rounded-sm py-3 px-4 font-sans text-sm text-ink focus:border-mint/50 outline-none" required />
                </div>
              </motion.div>
            )}
            {step === 1 && (
              <motion.div key="s1" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                   <div>
                    <label className="font-mono text-[10px] text-ink-faint uppercase tracking-[0.12em] mb-1.5 block">Country</label>
                    <select value={form.country_id || ''} onChange={(e) => update('country_id', e.target.value)} className="w-full bg-chalk border border-border-soft rounded-sm py-3 px-4 font-sans text-sm text-ink outline-none">
                      {countries?.map((c: any) => (
                        <option key={c.id} value={c.id}>{c.name}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="font-mono text-[10px] text-ink-faint uppercase tracking-[0.12em] mb-1.5 block">State / Region</label>
                    <input value={form.state || ''} onChange={(e) => update('state', e.target.value)} className="w-full bg-chalk border border-border-soft rounded-sm py-3 px-4 font-sans text-sm text-ink outline-none" required />
                  </div>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="font-mono text-[10px] text-ink-faint uppercase tracking-[0.12em] mb-1.5 block">City</label>
                    <input value={form.city || ''} onChange={(e) => update('city', e.target.value)} className="w-full bg-chalk border border-border-soft rounded-sm py-3 px-4 font-sans text-sm text-ink outline-none" required />
                  </div>
                  <div>
                    <label className="font-mono text-[10px] text-ink-faint uppercase tracking-[0.12em] mb-1.5 block">PIN / Zip Code</label>
                    <input value={form.pin_code || ''} onChange={(e) => update('pin_code', e.target.value)} className="w-full bg-chalk border border-border-soft rounded-sm py-3 px-4 font-sans text-sm text-ink outline-none" required />
                  </div>
                </div>
                {(!form.batch_slug || batches?.find((b: any) => b.slug === form.batch_slug)?.requires_document) && (
                <div className="pt-2">
                   <label className="font-mono text-xs text-ink-faint uppercase tracking-[0.12em] mb-2 block">Document Upload (Medical Registration)</label>
                   <div className="group relative">
                    <input 
                      type="file" 
                      onChange={async (e) => {
                        const file = e.target.files?.[0];
                        if (file) {
                          const formData = new FormData();
                          formData.append('file', file);
                          setLoading(true);
                          try {
                            const res = await apiClient('/registration/upload-document', {
                              method: 'POST',
                              body: formData
                            });
                            update('document_file', res.filename);
                          } catch (err: any) {
                            alert('Upload failed: ' + err.message);
                          } finally {
                            setLoading(false);
                          }
                        }
                      }}
                      className="w-full bg-chalk border border-border-soft rounded-sm py-3 px-4 font-sans text-sm text-ink focus:border-mint/50 outline-none file:mr-4 file:py-1 file:px-3 file:rounded-sm file:border-0 file:text-xs file:font-mono file:uppercase file:tracking-wider file:bg-slate file:text-chalk cursor-pointer" 
                    />
                    {form.document_file && <div className="mt-2 text-xs font-mono text-mint flex items-center gap-1"><Check size={10}/> Document uploaded: {form.document_file}</div>}
                   </div>
                   <p className="mt-2 font-sans text-xs leading-relaxed text-red-500/80 italic">
                    Note: Please upload your scanned copy of medical council registration certificate or its equivalent (e.g. State Medical Council, MCI). It should clearly show your photo and registration details.
                   </p>
                </div>
                )}
                <div className="pt-2">
                   <label className="font-mono text-[10px] text-ink-faint uppercase tracking-[0.12em] mb-2 block">Hospital / Institution</label>
                   <input value={form.hospital || ''} onChange={(e) => update('hospital', e.target.value)} placeholder="e.g. AIIMS Delhi" className="w-full bg-chalk border border-border-soft rounded-sm py-3 px-4 font-sans text-sm text-ink focus:border-mint/50 outline-none" required />
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                  <div>
                    <label className="font-mono text-[10px] text-ink-faint uppercase tracking-[0.12em] mb-1.5 block">Qualification</label>
                    <select value={form.qualification || ''} onChange={(e) => update('qualification', e.target.value)} className="w-full bg-chalk border border-border-soft rounded-sm py-3 px-4 font-sans text-sm text-ink outline-none">
                       <option value="">Select</option>
                       <option>MBBS</option><option>MD</option><option>DM</option><option>DNB</option><option>Other</option>
                    </select>
                  </div>
                  <div>
                    <label className="font-mono text-[10px] text-ink-faint uppercase tracking-[0.12em] mb-1.5 block">Speciality</label>
                    <input value={form.speciality || ''} onChange={(e) => update('speciality', e.target.value)} placeholder="e.g. Critical Care" className="w-full bg-chalk border border-border-soft rounded-sm py-3 px-4 font-sans text-sm text-ink outline-none" />
                  </div>
                </div>
                <div className="pt-4 border-t border-border-soft">
                  <label className="font-mono text-[10px] text-ink-faint uppercase tracking-[0.12em] mb-2 block">Choose Course</label>
                  <div className="grid grid-cols-1 gap-2">
                    {chooseCourseBatches.map((b: any) => (
                      <button
                        key={b.slug}
                        type="button"
                        onClick={() => update('batch_slug', b.slug)}
                        className={`flex items-center justify-between px-4 py-3 border rounded-sm transition-all ${
                          form.batch_slug === b.slug ? 'border-mint bg-mint-pale' : 'border-border-soft hover:bg-chalk'
                        }`}
                      >
                         <div className="flex items-center gap-3">
                            <div className={`w-3.5 h-3.5 rounded-full border flex items-center justify-center ${form.batch_slug === b.slug ? 'border-mint bg-mint' : 'border-border-strong'}`}>
                                {form.batch_slug === b.slug && <Check size={8} className="text-white" />}
                            </div>
                            <div className="font-sans text-sm font-bold text-slate">{b.displayTitle}</div>
                         </div>
                         <ChevronRight size={12} className="text-ink-faint" />
                      </button>
                    ))}
                  </div>
                </div>
              </motion.div>
            )}
            {step === 2 && (
              <motion.div key="s2" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }} className="space-y-4">
                <div className="font-mono text-xs text-ink-faint uppercase tracking-[0.12em] mb-3">Confirm Package & Payment</div>
                
                {pkgsLoading && <div className="py-12 text-center animate-pulse font-mono text-xs text-ink-faint">Evaluating regional pricing...</div>}
                
                <div className="space-y-3">
                  {packages?.map((p: any) => (
                    <label
                      key={p.id}
                      className={`flex items-center justify-between p-4 rounded-sm border cursor-pointer transition-all ${
                        form.package_id === String(p.id) ? 'border-mint bg-mint-pale' : 'border-border-soft hover:border-border-strong'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <input type="radio" name="package" value={p.id} checked={form.package_id === String(p.id)} onChange={() => update('package_id', String(p.id))} className="hidden" />
                        <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${form.package_id === String(p.id) ? 'border-mint' : 'border-border-strong'}`}>
                          {form.package_id === String(p.id) && <div className="w-2 rounded-full bg-mint h-2" />}
                        </div>
                        <div>
                          <div className="font-sans text-sm font-bold text-slate flex items-center gap-2">
                             {p.name}
                             {p.name.toLowerCase().includes('early') && <span className="bg-amber/10 text-amber text-[7px] px-1.5 py-0.5 rounded-sm uppercase border border-amber/20 flex items-center gap-1"><Sparkles size={7}/> Early Bird</span>}
                             {p.plan_type === 'subscription' && (
                               <span className="bg-mint-pale text-slate text-[9px] px-1.5 py-0.5 rounded-sm uppercase border border-mint/30">
                                 Subscription {formatDurationLabel(p.duration_months)}
                               </span>
                             )}
                             {p.plan_type !== 'subscription' && (
                               <span className="bg-ink-ghost text-slate text-[9px] px-1.5 py-0.5 rounded-sm uppercase border border-border-soft">
                                 One-time
                               </span>
                             )}
                          </div>
                          {foreignOfferText && form.package_id === String(p.id) && (
                            <p className="mt-1 font-sans text-[11px] font-semibold uppercase tracking-wide text-amber">
                              {foreignOfferText}
                            </p>
                          )}
                        </div>
                      </div>
                      <div className="font-display font-black text-lg text-slate">{packages[0]?.currency_name === 'USD' ? '$' : '₹'}{p.total_amount.toLocaleString()}</div>
                    </label>
                  ))}
                </div>

                {form.package_id && (
                  <div className="pt-4 space-y-4">
                    <div className="flex items-center gap-3">
                       <input 
                         value={form.coupon_code || ''} 
                         onChange={(e) => update('coupon_code', e.target.value)}
                         placeholder="Coupon Code (Optional)"
                         className="flex-1 bg-chalk border border-border-soft rounded-sm py-3 px-4 font-mono text-xs text-ink focus:border-mint/50 outline-none"
                       />
                    </div>
                    
                    <div className="mt-6 pt-6 border-t border-border-soft text-right">
                      <div className="font-mono text-xs text-ink-faint mb-1">TOTAL PAYABLE</div>
                      <div className="font-display font-black text-5xl text-mint leading-none">
                        {(payablePreview?.currency_name || packages?.find((p: any) => String(p.id) === form.package_id)?.currency_name) === 'USD' ? '$' : '₹'}
                        {Number(payablePreview?.total_amount ?? packages?.find((p: any) => String(p.id) === form.package_id)?.total_amount ?? 0).toLocaleString()}
                      </div>
                      <p className="font-sans text-xs text-ink-muted mt-4 text-center sm:text-right max-w-[300px] ml-auto">
                          Secure payment via Razorpay. Access will be enabled immediately after successful transaction.
                      </p>
                    </div>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>

          <div className="flex justify-between mt-10">
            {step > 0 && (
              <button type="button" onClick={() => setStep(step - 1)} className="border border-border-strong text-ink-secondary rounded-sm px-6 py-3 font-sans text-sm hover:border-slate-400 transition-all">
                ← Back
              </button>
            )}
            <button
              type="submit"
              disabled={loading}
              className={`magnetic rounded-sm px-8 py-3 min-h-[46px] font-sans font-semibold text-sm transition-all border ${step === 0 ? 'ml-auto' : ''} ${
                isPaymentStep
                  ? 'bg-slate text-chalk border-slate hover:bg-slate-light shadow-sm'
                  : 'bg-slate text-chalk border-slate hover:bg-slate-light'
              } disabled:opacity-60`}
            >
              <span className="inline-flex items-center justify-center w-full font-semibold tracking-[0.01em]">
                {loading ? 'Processing...' : isPaymentStep ? 'Pay & Register →' : 'Continue →'}
              </span>
            </button>
          </div>
        </form>

        <p className="font-sans text-[13px] text-ink-muted text-center mt-8">
          Already have an account?{' '}
          <Link to="/login" className="text-mint hover:text-mint-dark">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
