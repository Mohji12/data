import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/apiClient';
import { useIsTechAdmin } from '@/store/authStore';
import { Copy, Trash2 } from 'lucide-react';

const currencySymbol = (category?: string | null) =>
  category === 'Foreign Delegates' ? '$' : '₹';

/** HTML date inputs require yyyy-MM-dd; API may return MySQL datetimes. */
const toDateInputValue = (value?: string | null): string => {
  if (!value) return '';
  const raw = String(value).trim();
  return raw.length >= 10 ? raw.slice(0, 10) : raw;
};

const promoDescriptionOptionKey = (subscription: string) =>
  `package_promo_description::${subscription.trim()}`;

const promoShowcaseStartOptionKey = (subscription: string) =>
  `package_promo_showcase_start::${subscription.trim()}`;

function promoStatusLine(pctRaw: string | number, validTill: string, description: string) {
  const pct = Number(pctRaw || 0);
  if (!validTill) {
    return pct > 0
      ? `${pct}% ${description || 'discount'} · set Valid till for countdown`
      : 'Set discount % and valid till for the course cloud badge';
  }
  const till = new Date(`${validTill}T23:59:59+05:30`);
  const msLeft = till.getTime() - Date.now();
  const daysLeft = msLeft <= 0 ? 0 : Math.ceil(msLeft / (24 * 60 * 60 * 1000));
  const active = daysLeft > 0 && pct > 0;
  if (active) {
    return `${daysLeft} day${daysLeft === 1 ? '' : 's'} left (until ${validTill}) · ${pct}% ${description || 'discount'}`;
  }
  return `Inactive — expired or invalid (until ${validTill})`;
}

const normalizePackageRow = (p: PackageRow): PackageRow => ({
  ...p,
  start_date: toDateInputValue(p.start_date),
  end_date: toDateInputValue(p.end_date),
  batch_start_date: toDateInputValue(p.batch_start_date),
  discount_start_date: toDateInputValue(p.discount_start_date),
  discount_end_date: toDateInputValue(p.discount_end_date),
});

const packagePayloadFromRow = (p: PackageRow) => {
  const planType = p.plan_type || 'one_time';
  const discountPct = Number(p.discount_percentage || 0);
  const rawDuration = Number(p.duration_months || 0);
  const durationMonths =
    planType === 'subscription' ? (rawDuration > 0 ? rawDuration : 6) : null;

  return {
    name: p.name || '',
    subscription: p.subscription?.trim() || null,
    category_name: p.category_name || null,
    gross_amount: Number(p.gross_amount || 0),
    gst_percentage: Number(p.gst_percentage || 0),
    gst_amount: Number(p.gst_amount || 0),
    total_amount: Number(p.total_amount || 0),
    plan_type: planType,
    duration_months: durationMonths,
    start_date: toDateInputValue(p.start_date) || null,
    end_date: planType === 'subscription' ? null : toDateInputValue(p.end_date) || null,
    batch_start_date: toDateInputValue(p.batch_start_date) || null,
    with_topup: p.with_topup || '0',
    discount_percentage: discountPct,
    discounted_amount: discountPct > 0 ? Number(p.discounted_amount || 0) : 0,
    discount_start_date:
      discountPct > 0 ? toDateInputValue(p.discount_start_date) || null : null,
    discount_end_date: discountPct > 0 ? toDateInputValue(p.discount_end_date) || null : null,
    sync_promo_discount: true,
    status: p.status || '1',
  };
};

type PackageRow = {
  id: number;
  name: string;
  subscription?: string | null;
  category_name?: string | null;
  gross_amount?: number;
  gst_percentage?: number;
  gst_amount?: number;
  total_amount?: number;
  plan_type?: string | null;
  duration_months?: number | null;
  start_date?: string | null;
  end_date?: string | null;
  batch_start_date?: string | null;
  with_topup?: string | null;
  discount_percentage?: number;
  discounted_amount?: number;
  discount_start_date?: string | null;
  discount_end_date?: string | null;
  status?: string | null;
  /** Cloud badge label under % (stored in options per subscription) */
  promo_description?: string;
  /** Display-only “New Batch Starts From” date (options; not package.batch_start_date) */
  promo_showcase_start?: string;
};

type OptionRow = { id: number; option_name: string; option_value: string };
type BatchRow = { id: number; name: string; status: string };
export default function AdminPackages() {
  const qc = useQueryClient();
  const isTech = useIsTechAdmin();
  const [q, setQ] = useState('');
  const [sortBy, setSortBy] = useState<string>('id');
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');
  const [editing, setEditing] = useState<PackageRow | null>(null);
  const [form, setForm] = useState({
    name: '',
    subscription: '',
    category_name: 'Indian Delegates',
    gross_amount: '0',
    gst_percentage: '18',
    gst_amount: '0',
    total_amount: '0',
    plan_type: 'one_time',
    duration_months: '',
    start_date: '',
    end_date: '',
    batch_start_date: '',
    with_topup: '0',
    discount_percentage: '0',
    discounted_amount: '0',
    discount_start_date: '',
    discount_end_date: '',
    promo_description: 'discount',
    promo_showcase_start: '',
    status: '1',
  });
  const [isManualDurationAdd, setIsManualDurationAdd] = useState(false);
  const [isManualDurationEdit, setIsManualDurationEdit] = useState(false);

  const { data: rows, isLoading, error } = useQuery({
    queryKey: ['adminPackages', q, sortBy, order],
    queryFn: async () => {
      const p = new URLSearchParams();
      if (q.trim()) p.set('q', q.trim());
      p.set('sort_by', sortBy);
      p.set('order', order);
      const list = (await apiClient(`/admin/commerce/packages?${p.toString()}`)) as PackageRow[];
      return list.map(normalizePackageRow);
    },
  });

  const { data: batches } = useQuery({
    queryKey: ['adminMiscBatches'],
    queryFn: () => apiClient('/admin/misc/batches') as Promise<BatchRow[]>,
  });
  const { data: options } = useQuery({
    queryKey: ['adminCommerceOptions'],
    queryFn: () => apiClient('/admin/commerce/options') as Promise<OptionRow[]>,
  });
  const activeBatches = (batches || []).filter((b) => String(b.status ?? '1') === '1');

  const optionMap = new Map<string, string>();
  for (const row of options || []) {
    if (row.option_name) optionMap.set(row.option_name, row.option_value ?? '');
  }

  const savePromoBadgeOptions = async (
    subscription: string,
    description: string,
    showcaseStart: string,
  ) => {
    const sub = subscription.trim();
    if (!sub || !isTech) return;
    const desc = (description || 'discount').trim() || 'discount';
    const start = toDateInputValue(showcaseStart) || '';
    // Course-scoped: same Subscription name is shared by all packages for that course
    // (Indian/Foreign, all duration tiers). Persist once under the subscription key.
    await Promise.all([
      apiClient('/admin/commerce/options', {
        method: 'POST',
        body: JSON.stringify({
          option_name: promoDescriptionOptionKey(sub),
          option_value: desc,
        }),
      }),
      apiClient('/admin/commerce/options', {
        method: 'POST',
        body: JSON.stringify({
          option_name: promoShowcaseStartOptionKey(sub),
          option_value: start,
        }),
      }),
    ]);
    void qc.invalidateQueries({ queryKey: ['adminCommerceOptions'] });
    void qc.invalidateQueries({ queryKey: ['feeStructure'] });
  };

  const copyMut = useMutation({
    mutationFn: (id: number) => apiClient(`/admin/commerce/packages/${id}/copy`, { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['adminPackages'] }),
  });
  const createMut = useMutation({
    mutationFn: async () => {
      await apiClient('/admin/commerce/packages', {
        method: 'POST',
        body: JSON.stringify({
          ...form,
          gross_amount: Number(form.gross_amount || 0),
          gst_percentage: Number(form.gst_percentage || 0),
          gst_amount: Number(form.gst_amount || 0),
          total_amount: Number(form.total_amount || 0),
          plan_type: form.plan_type,
          duration_months: form.plan_type === 'subscription' ? Number(form.duration_months || 0) : null,
          subscription: form.subscription.trim() || null,
          start_date: toDateInputValue(form.start_date) || null,
          end_date: form.plan_type === 'subscription' ? null : toDateInputValue(form.end_date) || null,
          batch_start_date: toDateInputValue(form.batch_start_date) || null,
          discount_percentage: Number(form.discount_percentage || 0),
          discounted_amount: Number(form.discounted_amount || 0),
          discount_start_date: toDateInputValue(form.discount_start_date) || null,
          discount_end_date: toDateInputValue(form.discount_end_date) || null,
        }),
      });
      await savePromoBadgeOptions(form.subscription, form.promo_description, form.promo_showcase_start);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['adminPackages'] });
      qc.invalidateQueries({ queryKey: ['registrationCatalogNavbar'] });
      qc.invalidateQueries({ queryKey: ['registrationCatalogNavbarUnified'] });
      qc.invalidateQueries({ queryKey: ['regBatchesNavbar'] });
      setForm({
        name: '',
        subscription: '',
        category_name: 'Indian Delegates',
        gross_amount: '0',
        gst_percentage: '18',
        gst_amount: '0',
        total_amount: '0',
        plan_type: 'one_time',
        duration_months: '',
        start_date: '',
        end_date: '',
        batch_start_date: '',
        with_topup: '0',
        discount_percentage: '0',
        discounted_amount: '0',
        discount_start_date: '',
        discount_end_date: '',
        promo_description: 'discount',
        promo_showcase_start: '',
        status: '1',
      });
    },
  });
  const updateMut = useMutation({
    mutationFn: async (p: PackageRow) => {
      await apiClient(`/admin/commerce/packages/${p.id}`, {
        method: 'PUT',
        body: JSON.stringify(packagePayloadFromRow(p)),
      });
      await savePromoBadgeOptions(
        p.subscription || '',
        p.promo_description || 'discount',
        p.promo_showcase_start || '',
      );
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['adminPackages'] });
      qc.invalidateQueries({ queryKey: ['adminBatchLaunchReadiness'] });
      setEditing(null);
    },
    onError: (err: Error) => {
      window.alert(err.message || 'Failed to save package');
    },
  });
  const deleteMut = useMutation({
    mutationFn: (id: number) =>
      apiClient(`/admin/commerce/packages/${id}`, {
        method: 'DELETE',
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['adminPackages'] });
      qc.invalidateQueries({ queryKey: ['adminBatchLaunchReadiness'] });
      qc.invalidateQueries({ queryKey: ['registrationCatalogNavbar'] });
      qc.invalidateQueries({ queryKey: ['registrationCatalogNavbarUnified'] });
      qc.invalidateQueries({ queryKey: ['regBatchesNavbar'] });
      qc.invalidateQueries({ queryKey: ['regPackages'] });
    },
  });

  const calculateAddForm = (gross: string, gstPct: string, discountPct?: string) => {
    const g = parseFloat(gross) || 0;
    const p = parseFloat(gstPct) || 0;
    const dist_pct = parseFloat(discountPct ?? form.discount_percentage) || 0;
    const dist_amt = (g * dist_pct) / 100;
    const taxable = g - dist_amt;
    const amt = (taxable * p) / 100;
    const total = taxable + amt;
    
    setForm((prev) => ({
      ...prev,
      gross_amount: gross,
      gst_percentage: gstPct,
      discount_percentage: discountPct ?? prev.discount_percentage,
      gst_amount: String(Math.round(amt)),
      discounted_amount: String(Math.round(dist_amt)),
      total_amount: String(Math.round(total)),
    }));
  };

  const calculateEditForm = (gross: number, gstPct: number, discountPct?: number) => {
    if (!editing) return;
    const g = gross;
    const p = gstPct;
    const dist_pct = discountPct ?? (editing.discount_percentage || 0);
    const dist_amt = (g * dist_pct) / 100;
    const taxable = g - dist_amt;
    const amt = (taxable * p) / 100;
    const total = taxable + amt;

    setEditing({
      ...editing,
      gross_amount: gross,
      gst_percentage: gstPct,
      gst_amount: Math.round(amt),
      discount_percentage: dist_pct,
      discounted_amount: Math.round(dist_amt),
      total_amount: Math.round(total),
      ...(dist_pct <= 0
        ? { discount_start_date: '', discount_end_date: '' }
        : {}),
    });
  };

  const handleStartDateChange = (val: string, isEdit = false) => {
    if (!val) return;
    const planType = isEdit ? (editing?.plan_type || 'one_time') : form.plan_type;

    if (isEdit && editing) {
      setEditing({
        ...editing,
        start_date: val,
        batch_start_date: val,
        end_date: planType === 'subscription' ? null : editing.end_date
      });
    } else {
      setForm((f) => ({
        ...f,
        start_date: val,
        batch_start_date: val,
        end_date: planType === 'subscription' ? '' : f.end_date
      }));
    }
  };

  const toggleSort = (field: string) => {
    if (sortBy === field) {
      setOrder(order === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setOrder('desc');
    }
  };

  const SortIcon = ({ field }: { field: string }) => {
    if (sortBy !== field) return <span className="opacity-20 ml-1">↕</span>;
    return <span className="ml-1 text-mint">{order === 'asc' ? '↑' : '↓'}</span>;
  };

  return (
    <div className="p-6 lg:p-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="font-display font-bold text-3xl text-slate">Packages</h1>
          <p className="font-mono text-[11px] text-ink-faint mt-1 uppercase tracking-wider">
            Commerce packages (create / edit / copy requires tech admin)
          </p>
        </div>
        <div className="sm:w-64">
          <input
            type="text"
            placeholder="Search package name..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="w-full bg-chalk border border-border-soft rounded-sm py-2 px-3 font-sans text-sm outline-none focus:border-mint/50"
          />
        </div>
      </div>
      {isTech && (
        <div className="mb-6 bg-chalk border border-border-soft rounded-sm p-4 space-y-3">
          <h3 className="font-sans text-sm font-semibold text-slate">Add fee row for batch</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label className="block font-mono text-[10px] text-ink-faint mb-1">name</label>
              <input className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm" placeholder="Package name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div>
              <label className="block font-mono text-[10px] text-ink-faint mb-1">subscription</label>
              <select
                className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
                value={form.subscription}
                onChange={(e) => setForm({ ...form, subscription: e.target.value })}
              >
                <option value="">Select Batch</option>
                {activeBatches.map((b) => (
                  <option key={b.id} value={b.name}>
                    {b.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block font-mono text-[10px] text-ink-faint mb-1">category_name</label>
              <select className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm" value={form.category_name} onChange={(e) => setForm({ ...form, category_name: e.target.value })}>
                <option value="Indian Delegates">Indian Delegates</option>
                <option value="Foreign Delegates">Foreign Delegates</option>
              </select>
            </div>
            <div>
              <label className="block font-mono text-[10px] text-ink-faint mb-1">gross_amount</label>
              <input type="number" className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm" placeholder="Gross" value={form.gross_amount} onChange={(e) => calculateAddForm(e.target.value, form.gst_percentage)} />
            </div>
            <div>
              <label className="block font-mono text-[10px] text-ink-faint mb-1">gst_percentage</label>
              <input type="number" className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm" placeholder="GST %" value={form.gst_percentage} onChange={(e) => calculateAddForm(form.gross_amount, e.target.value)} />
            </div>
            <div>
              <label className="block font-mono text-[10px] text-ink-faint mb-1">gst_amount</label>
              <input type="number" className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm" placeholder="GST amount" value={form.gst_amount} onChange={(e) => setForm({ ...form, gst_amount: e.target.value })} />
            </div>
            <div>
              <label className="block font-mono text-[10px] text-ink-faint mb-1">total_amount</label>
              <input type="number" className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm" placeholder="Total amount" value={form.total_amount} onChange={(e) => setForm({ ...form, total_amount: e.target.value })} />
            </div>
            <div>
              <label className="block font-mono text-[10px] text-ink-faint mb-1">plan_type</label>
              <select className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm" value={form.plan_type} onChange={(e) => setForm({ ...form, plan_type: e.target.value, duration_months: e.target.value === 'subscription' ? form.duration_months : '' })}>
                <option value="one_time">One-time</option>
                <option value="subscription">Subscription</option>
              </select>
            </div>
            <div>
              <label className="block font-mono text-[10px] text-ink-faint mb-1">duration_months</label>
              <div className="flex gap-2">
                {!isManualDurationAdd ? (
                  <select
                    className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
                    value={form.duration_months}
                    disabled={form.plan_type !== 'subscription'}
                    onChange={(e) => {
                      if (e.target.value === 'manual') {
                        setIsManualDurationAdd(true);
                        setForm({ ...form, duration_months: '' });
                      } else {
                        setForm({ ...form, duration_months: e.target.value });
                      }
                    }}
                  >
                    <option value="">N/A</option>
                    <option value="6">6</option>
                    <option value="9">9</option>
                    <option value="12">12</option>
                    <option value="manual">Other (Manual)...</option>
                  </select>
                ) : (
                  <div className="relative w-full">
                    <input
                      type="number"
                      className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm pr-10"
                      placeholder="Months"
                      value={form.duration_months}
                      onChange={(e) => setForm({ ...form, duration_months: e.target.value })}
                    />
                    <button
                      type="button"
                      onClick={() => {
                        setIsManualDurationAdd(false);
                        setForm({ ...form, duration_months: '' });
                      }}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-blush hover:underline"
                    >
                      Reset
                    </button>
                  </div>
                )}
              </div>
            </div>
            <div>
              <label className="block font-mono text-[10px] text-ink-faint mb-1">start_date</label>
              <input type="date" className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm" value={form.start_date} onChange={(e) => handleStartDateChange(e.target.value)} />
            </div>
            <div>
              <label className="block font-mono text-[10px] text-ink-faint mb-1">end_date</label>
              <input
                type="date"
                disabled={form.plan_type === 'subscription'}
                className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm disabled:opacity-60"
                value={form.end_date}
                onChange={(e) => setForm({ ...form, end_date: e.target.value })}
              />
              {form.plan_type === 'subscription' && (
                <p className="mt-1 font-mono text-[10px] text-ink-faint">
                  Subscriptions expire from user registration date + duration months.
                </p>
              )}
            </div>
            <div>
              <label className="block font-mono text-[10px] text-ink-faint mb-1">batch_start_date</label>
              <input type="date" className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm" value={form.batch_start_date} onChange={(e) => setForm({ ...form, batch_start_date: e.target.value })} />
            </div>
            <div>
              <label className="block font-mono text-[10px] text-ink-faint mb-1">with_topup</label>
              <select className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm" value={form.with_topup} onChange={(e) => setForm({ ...form, with_topup: e.target.value })}>
                <option value="0">No topup</option>
                <option value="1">With topup</option>
              </select>
            </div>
            <div>
              <label className="block font-mono text-[10px] text-ink-faint mb-1">status</label>
              <select className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
                <option value="1">Active</option>
                <option value="0">Inactive</option>
              </select>
            </div>
          </div>

          <div className="mt-5 rounded-sm border border-border-soft bg-chalk p-4 sm:p-5">
            <h3 className="font-display font-bold text-base text-slate mb-1">Course promo badge</h3>
            <p className="font-sans text-xs text-ink-muted mb-4">
              Cloud discount for this course description page. Discount % / dates sync across subscription tiers;
              Description and <strong className="font-semibold">New batch starts from</strong> apply to{' '}
              <strong className="font-semibold">all packages</strong> that share this Subscription (batch) name.
            </p>
            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">Discount %</label>
                <input
                  type="number"
                  min={0}
                  max={100}
                  className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
                  placeholder="25"
                  value={form.discount_percentage}
                  onChange={(e) => calculateAddForm(form.gross_amount, form.gst_percentage, e.target.value)}
                />
              </div>
              <div className="sm:col-span-2">
                <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">Description</label>
                <input
                  type="text"
                  maxLength={40}
                  className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
                  placeholder="discount"
                  value={form.promo_description}
                  onChange={(e) => setForm({ ...form, promo_description: e.target.value })}
                />
              </div>
              <div>
                <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">Valid till</label>
                <input
                  type="date"
                  className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
                  value={form.discount_end_date}
                  onChange={(e) => setForm({ ...form, discount_end_date: e.target.value })}
                />
              </div>
              <div>
                <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">Discount start (optional)</label>
                <input
                  type="date"
                  className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
                  value={form.discount_start_date}
                  onChange={(e) => setForm({ ...form, discount_start_date: e.target.value })}
                />
              </div>
              <div>
                <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">Discounted amount</label>
                <input type="number" readOnly className="w-full bg-ink-ghost border border-border-soft rounded-sm py-2 px-3 text-sm" value={form.discounted_amount} />
              </div>
              <div className="sm:col-span-3">
                <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">
                  New batch starts from (showcase)
                </label>
                <input
                  type="date"
                  className="w-full max-w-xs bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
                  value={form.promo_showcase_start}
                  onChange={(e) => setForm({ ...form, promo_showcase_start: e.target.value })}
                />
                <p className="mt-1 font-sans text-[10px] text-ink-faint">
                  Display only. Shared for all packages of this course — does not change package access dates.
                </p>
              </div>
            </div>
            <p
              className={`mt-3 font-mono text-[11px] ${
                Number(form.discount_percentage) > 0 && form.discount_end_date ? 'text-mint' : 'text-ink-faint'
              }`}
            >
              {promoStatusLine(form.discount_percentage, form.discount_end_date, form.promo_description)}
            </p>
          </div>

          <button
            type="button"
            disabled={
              !form.name.trim() ||
              !form.subscription.trim() ||
              (form.plan_type === 'subscription' && (!form.duration_months || isNaN(Number(form.duration_months)))) ||
              createMut.isPending
            }
            onClick={() => createMut.mutate()}
            className="magnetic bg-slate text-chalk rounded-sm px-4 py-2 font-sans text-xs font-semibold hover:bg-slate-light disabled:opacity-50 mt-4"
          >
            {createMut.isPending ? 'Adding…' : 'Add fee'}
          </button>
        </div>
      )}

      {isLoading && <div className="font-mono text-xs text-ink-faint py-12 text-center animate-pulse">Loading packages…</div>}
      {error && <div className="text-red-600 font-sans text-sm py-6">Failed to load packages.</div>}

      <div className="bg-chalk border border-border-soft rounded-sm overflow-x-auto">
        <table className="w-full min-w-[720px]">
          <thead>
            <tr className="bg-chalk-cool border-b border-border-soft">
              {[
                { id: 'id', label: 'ID' },
                { id: 'name', label: 'Name' },
                { id: 'subscription', label: 'Subscription' },
                { id: 'category_name', label: 'Category' },
                { label: 'Plan' },
                { label: 'Duration' },
                { id: 'gross_amount', label: 'Gross' },
                { label: 'Discount' },
                { label: 'Taxable' },
                { label: 'GST' },
                { id: 'total_amount', label: 'Payable' },
                { label: 'Date Window' },
                { label: 'Status' },
                { label: 'Topup' },
                { label: '' },
              ].map((h) => (
                <th
                  key={h.label}
                  onClick={() => 'id' in h && h.id && toggleSort(h.id)}
                  className={`font-mono text-[10px] text-ink-faint uppercase tracking-wider text-left px-4 py-3 whitespace-nowrap ${
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
            {(rows || []).map((p) => (
              <tr key={p.id} className="border-b border-border-soft hover:bg-ink-ghost">
                <td className="px-4 py-3 font-mono text-xs text-ink-faint">#{p.id}</td>
                <td className="px-4 py-3 font-sans text-sm text-slate font-medium">{p.name}</td>
                <td className="px-4 py-3 font-mono text-[11px] text-ink-muted">{p.subscription || '—'}</td>
                <td className="px-4 py-3 font-mono text-[11px] text-ink-muted">{p.category_name || '—'}</td>
                <td className="px-4 py-3 font-mono text-[10px]">{p.plan_type === 'subscription' ? 'Subscription' : 'One-time'}</td>
                <td className="px-4 py-3 font-mono text-[10px]">{p.duration_months || '—'}</td>
                <td className="px-4 py-3 font-mono text-xs text-ink-muted italic">{currencySymbol(p.category_name)}{Number(p.gross_amount ?? 0).toLocaleString()}</td>
                <td className="px-4 py-3 font-mono text-[10px]">
                  {p.discount_percentage ? (
                    <div className="flex flex-col">
                      <span className="text-mint font-bold">{p.discount_percentage}% off</span>
                      <span className="text-ink-faint text-[9px]">-{currencySymbol(p.category_name)}{p.discounted_amount}</span>
                    </div>
                  ) : '—'}
                </td>
                <td className="px-4 py-3 font-mono text-xs text-ink-muted">{currencySymbol(p.category_name)}{Number((p.gross_amount ?? 0) - (p.discounted_amount ?? 0)).toLocaleString()}</td>
                <td className="px-4 py-3 font-mono text-xs text-ink-muted italic">
                  <div className="flex flex-col">
                    <span className="text-ink-faint text-[9px]">{p.gst_percentage}%</span>
                    <span>{currencySymbol(p.category_name)}{Number(p.gst_amount ?? 0).toLocaleString()}</span>
                  </div>
                </td>
                <td className="px-4 py-3 font-mono text-sm text-slate font-bold">{currencySymbol(p.category_name)}{Number(p.total_amount ?? 0).toLocaleString()}</td>
                <td className="px-4 py-3 font-mono text-[10px]">
                  {p.start_date || '—'} to {p.end_date || '—'}
                </td>
                <td className="px-4 py-3 font-mono text-[10px]">{p.status === '1' ? 'Active' : 'Off'}</td>
                <td className="px-4 py-3 font-mono text-[10px]">{p.with_topup === '1' ? 'Yes' : 'No'}</td>
                <td className="px-4 py-3">
                  {isTech ? (
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          const row = normalizePackageRow(p);
                          const sub = (row.subscription || '').trim();
                          setEditing({
                            ...row,
                            promo_description:
                              (sub && optionMap.get(promoDescriptionOptionKey(sub))) || 'discount',
                            promo_showcase_start:
                              (sub && optionMap.get(promoShowcaseStartOptionKey(sub))) || '',
                          });
                        }}
                        className="inline-flex items-center gap-1.5 text-xs font-sans text-slate border border-border-soft rounded-sm px-2 py-1"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        disabled={copyMut.isPending}
                        onClick={() => copyMut.mutate(p.id)}
                        className="inline-flex items-center gap-1.5 text-xs font-sans text-mint hover:text-mint-dark border border-mint/30 rounded-sm px-2 py-1 disabled:opacity-50"
                      >
                        <Copy size={12} />
                        Copy
                      </button>
                      <button
                        type="button"
                        disabled={deleteMut.isPending}
                        onClick={() => {
                          if (!window.confirm(`Delete package #${p.id}? This will remove it from student registration.`)) return;
                          deleteMut.mutate(p.id);
                        }}
                        className="inline-flex items-center gap-1.5 text-xs font-sans text-blush hover:text-blush border border-blush/40 rounded-sm px-2 py-1 disabled:opacity-50"
                      >
                        <Trash2 size={12} />
                        Delete
                      </button>
                    </div>
                  ) : (
                    <span className="font-mono text-[10px] text-ink-faint">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!isLoading && (rows || []).length === 0 && (
          <div className="p-12 text-center font-sans text-sm text-ink-muted">No packages found.</div>
        )}
      </div>
      {editing && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4 overflow-y-auto">
          <div className="w-full max-w-3xl max-h-[min(92vh,900px)] bg-chalk border border-border-soft rounded-sm flex flex-col my-auto shadow-lg">
            <div className="shrink-0 px-5 pt-5 pb-3 border-b border-border-soft">
              <h3 className="font-display font-bold text-xl text-slate">Edit fee row</h3>
            </div>
            <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain px-5 py-4 space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <input className="bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm" value={editing.name || ''} onChange={(e) => setEditing({ ...editing, name: e.target.value })} />
              <select
                className="bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
                value={editing.subscription || ''}
                onChange={(e) => setEditing({ ...editing, subscription: e.target.value })}
              >
                <option value="">Select Batch</option>
                {activeBatches.map((b) => (
                  <option key={b.id} value={b.name}>
                    {b.name}
                  </option>
                ))}
              </select>
              <select className="bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm" value={editing.category_name || 'Indian Delegates'} onChange={(e) => setEditing({ ...editing, category_name: e.target.value })}>
                <option value="Indian Delegates">Indian Delegates</option>
                <option value="Foreign Delegates">Foreign Delegates</option>
              </select>
              <input type="number" className="bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm" value={editing.gross_amount ?? 0} onChange={(e) => calculateEditForm(Number(e.target.value || 0), editing.gst_percentage ?? 18)} />
              <input type="number" className="bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm" value={editing.gst_percentage ?? 0} onChange={(e) => calculateEditForm(editing.gross_amount ?? 0, Number(e.target.value || 0))} />
              <input type="number" className="bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm" value={editing.gst_amount ?? 0} onChange={(e) => setEditing({ ...editing, gst_amount: Number(e.target.value || 0) })} />
              <input type="number" className="bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm" value={editing.total_amount ?? 0} onChange={(e) => setEditing({ ...editing, total_amount: Number(e.target.value || 0) })} />
              <select
                className="bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
                value={editing.plan_type || 'one_time'}
                onChange={(e) =>
                  setEditing({
                    ...editing,
                    plan_type: e.target.value,
                    duration_months: e.target.value === 'subscription' ? (editing.duration_months ?? 6) : null,
                    end_date: e.target.value === 'subscription' ? null : editing.end_date,
                  })
                }
              >
                <option value="one_time">One-time</option>
                <option value="subscription">Subscription</option>
              </select>
              <div>
                <label className="block font-mono text-[10px] text-ink-faint mb-1">duration_months</label>
                <div className="flex gap-2">
                  {!isManualDurationEdit && (editing.duration_months === null || [6, 9, 12].includes(editing.duration_months)) ? (
                    <select
                      className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
                      value={editing.duration_months ?? ''}
                      disabled={(editing.plan_type || 'one_time') !== 'subscription'}
                      onChange={(e) => {
                        if (e.target.value === 'manual') {
                          setIsManualDurationEdit(true);
                        } else {
                          setEditing({ ...editing, duration_months: Number(e.target.value || 0) || null });
                        }
                      }}
                    >
                      <option value="">N/A</option>
                      <option value="6">6</option>
                      <option value="9">9</option>
                      <option value="12">12</option>
                      <option value="manual">Other (Manual)...</option>
                    </select>
                  ) : (
                    <div className="relative w-full">
                      <input
                        type="number"
                        className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm pr-10"
                        placeholder="Months"
                        value={editing.duration_months ?? ''}
                        onChange={(e) => setEditing({ ...editing, duration_months: Number(e.target.value || 0) || null })}
                      />
                      <button
                        type="button"
                        onClick={() => {
                          setIsManualDurationEdit(false);
                          setEditing({ ...editing, duration_months: 6 });
                        }}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-blush hover:underline"
                      >
                        Select
                      </button>
                    </div>
                  )}
                </div>
              </div>
              <input type="date" className="bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm" value={editing.start_date || ''} onChange={(e) => handleStartDateChange(e.target.value, true)} />
              <div>
                <input
                  type="date"
                  disabled={(editing.plan_type || 'one_time') === 'subscription'}
                  className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm disabled:opacity-60"
                  value={editing.end_date || ''}
                  onChange={(e) => setEditing({ ...editing, end_date: e.target.value })}
                />
                {(editing.plan_type || 'one_time') === 'subscription' && (
                  <p className="mt-1 font-mono text-[10px] text-ink-faint">
                    Subscriptions expire from user registration date + duration months.
                  </p>
                )}
              </div>
              <input type="date" className="bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm" value={editing.batch_start_date || ''} onChange={(e) => setEditing({ ...editing, batch_start_date: e.target.value })} />
              <select className="bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm" value={editing.with_topup || '0'} onChange={(e) => setEditing({ ...editing, with_topup: e.target.value })}>
                <option value="0">No topup</option>
                <option value="1">With topup</option>
              </select>
              <select className="bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm" value={editing.status || '1'} onChange={(e) => setEditing({ ...editing, status: e.target.value })}>
                <option value="1">Active</option>
                <option value="0">Inactive</option>
              </select>
            </div>

            <div className="rounded-sm border border-border-soft bg-chalk-warm/40 p-4">
              <h3 className="font-display font-bold text-base text-slate mb-1">Course promo badge</h3>
              <p className="font-sans text-xs text-ink-muted mb-4">
                Applies to the course cloud for <strong className="font-semibold">every package</strong> with this
                Subscription name (all durations / Indian &amp; Foreign). Discount % still syncs across tiers via Save.
              </p>
              <div className="grid gap-4 sm:grid-cols-3">
                <div>
                  <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">Discount %</label>
                  <input
                    type="number"
                    min={0}
                    max={100}
                    className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
                    value={editing.discount_percentage || 0}
                    onChange={(e) => calculateEditForm(editing.gross_amount ?? 0, editing.gst_percentage ?? 18, Number(e.target.value || 0))}
                  />
                </div>
                <div className="sm:col-span-2">
                  <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">Description</label>
                  <input
                    type="text"
                    maxLength={40}
                    className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
                    value={editing.promo_description || 'discount'}
                    onChange={(e) => setEditing({ ...editing, promo_description: e.target.value })}
                  />
                </div>
                <div>
                  <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">Valid till</label>
                  <input
                    type="date"
                    className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
                    value={editing.discount_end_date || ''}
                    onChange={(e) => setEditing({ ...editing, discount_end_date: e.target.value })}
                  />
                </div>
                <div>
                  <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">Discount start (optional)</label>
                  <input
                    type="date"
                    className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
                    value={editing.discount_start_date || ''}
                    onChange={(e) => setEditing({ ...editing, discount_start_date: e.target.value })}
                  />
                </div>
                <div>
                  <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">Discounted amount</label>
                  <input type="number" readOnly className="w-full bg-ink-ghost border border-border-soft rounded-sm py-2 px-3 text-sm" value={editing.discounted_amount || 0} />
                </div>
                <div className="sm:col-span-3">
                  <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">
                    New batch starts from (showcase)
                  </label>
                  <input
                    type="date"
                    className="w-full max-w-xs bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
                    value={editing.promo_showcase_start || ''}
                    onChange={(e) => setEditing({ ...editing, promo_showcase_start: e.target.value })}
                  />
                  <p className="mt-1 font-sans text-[10px] text-ink-faint">
                    Display only. Shared across all packages for this course — does not change access dates.
                  </p>
                </div>
              </div>
              <p
                className={`mt-3 font-mono text-[11px] ${
                  Number(editing.discount_percentage) > 0 && editing.discount_end_date ? 'text-mint' : 'text-ink-faint'
                }`}
              >
                {promoStatusLine(
                  editing.discount_percentage || 0,
                  editing.discount_end_date || '',
                  editing.promo_description || 'discount',
                )}
              </p>
            </div>
            </div>

            <div className="shrink-0 flex justify-end gap-2 px-5 py-3 border-t border-border-soft bg-chalk">
              <button type="button" className="px-3 py-2 text-xs border border-border-soft rounded-sm" onClick={() => setEditing(null)}>Cancel</button>
              <button
                type="button"
                className="px-3 py-2 text-xs bg-slate text-chalk rounded-sm disabled:opacity-50"
                disabled={!editing.name?.trim() || updateMut.isPending}
                onClick={() => updateMut.mutate(editing)}
              >
                {updateMut.isPending ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
