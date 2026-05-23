import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { apiClient } from '@/lib/apiClient';

type DashboardProfile = {
  id: number;
  registration_type?: string | null;
  subscription?: string | null;
  title?: string | null;
  name?: string | null;
  email: string;
  contact_number?: string | null;
  hospital?: string | null;
  qualification?: string | null;
  speciality?: string | null;
  country_id?: number | null;
  state?: string | null;
  city?: string | null;
  pin_code?: string | null;
  currency_name?: string | null;
  payment_status?: string | null;
  approve?: string | null;
};

type ProfileFormState = {
  title: string;
  name: string;
  contact_number: string;
  hospital: string;
  qualification: string;
  speciality: string;
  country_id: string;
  state: string;
  city: string;
  pin_code: string;
};

function toFormState(profile: DashboardProfile): ProfileFormState {
  return {
    title: profile.title || '',
    name: profile.name || '',
    contact_number: profile.contact_number || '',
    hospital: profile.hospital || '',
    qualification: profile.qualification || '',
    speciality: profile.speciality || '',
    country_id: profile.country_id != null ? String(profile.country_id) : '',
    state: profile.state || '',
    city: profile.city || '',
    pin_code: profile.pin_code || '',
  };
}

export default function Profile() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ['dashboardProfile'],
    queryFn: () => apiClient('/dashboard/profile') as Promise<DashboardProfile>,
  });

  // Block right-click completely on the entire profile section
  useEffect(() => {
    const blockMenu = (e: MouseEvent) => {
      e.preventDefault();
    };
    document.addEventListener('contextmenu', blockMenu, true);
    return () => {
      document.removeEventListener('contextmenu', blockMenu, true);
    };
  }, []);

  const [form, setForm] = useState<ProfileFormState>({
    title: '',
    name: '',
    contact_number: '',
    hospital: '',
    qualification: '',
    speciality: '',
    country_id: '',
    state: '',
    city: '',
    pin_code: '',
  });

  useEffect(() => {
    if (!data) return;
    setForm(toFormState(data));
  }, [data]);

  const saveMut = useMutation({
    mutationFn: () =>
      apiClient('/dashboard/profile', {
        method: 'PUT',
        body: JSON.stringify({
          title: form.title.trim() || null,
          name: form.name.trim() || null,
          contact_number: form.contact_number.trim() || null,
          hospital: form.hospital.trim() || null,
          qualification: form.qualification.trim() || null,
          speciality: form.speciality.trim() || null,
          country_id: form.country_id.trim() ? Number(form.country_id) : null,
          state: form.state.trim() || null,
          city: form.city.trim() || null,
          pin_code: form.pin_code.trim() || null,
        }),
      }) as Promise<DashboardProfile>,
    onSuccess: (next) => {
      qc.setQueryData(['dashboardProfile'], next);
      toast.success('Profile updated successfully');
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const setField = (key: keyof ProfileFormState, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  if (isLoading) {
    return <div className="p-6 lg:p-8 font-mono text-xs text-ink-faint animate-pulse">Loading profile...</div>;
  }

  return (
    <div className="p-6 lg:p-8">
      <h1 className="font-display font-bold text-3xl text-slate mb-8">Profile</h1>
      <div className="max-w-[860px] bg-chalk border border-border-soft rounded-sm p-8">
        <div className="flex items-center gap-4 mb-8">
          <div className="w-16 h-16 rounded-sm bg-mint-pale border border-mint/30 flex items-center justify-center font-mono text-xl text-slate font-bold">
            {(data?.name || 'U').slice(0, 2).toUpperCase()}
          </div>
          <div>
            <div className="font-sans font-semibold text-lg text-ink">{data?.name || 'User'}</div>
            <div className="font-mono text-xs text-ink-faint">{data?.subscription || '—'}</div>
          </div>
        </div>
        <form
          className="space-y-5"
          onSubmit={(e) => {
            e.preventDefault();
            saveMut.mutate();
          }}
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <div>
              <label className="font-mono text-[11px] text-ink-faint uppercase tracking-[0.12em] mb-2 block">Title</label>
              <input value={form.title} onChange={(e) => setField('title', e.target.value)} className="w-full bg-chalk-warm border border-border-soft rounded-sm py-3 px-4 font-sans text-sm text-ink focus:border-mint/50 outline-none" />
            </div>
            <div>
              <label className="font-mono text-[11px] text-ink-faint uppercase tracking-[0.12em] mb-2 block">Full Name</label>
              <input value={form.name} onChange={(e) => setField('name', e.target.value)} className="w-full bg-chalk-warm border border-border-soft rounded-sm py-3 px-4 font-sans text-sm text-ink focus:border-mint/50 outline-none" />
            </div>
            <div>
              <label className="font-mono text-[11px] text-ink-faint uppercase tracking-[0.12em] mb-2 block">Email</label>
              <input value={data?.email || ''} disabled className="w-full bg-chalk-stone border border-border-soft rounded-sm py-3 px-4 font-sans text-sm text-ink-muted" />
            </div>
            <div>
              <label className="font-mono text-[11px] text-ink-faint uppercase tracking-[0.12em] mb-2 block">Contact Number</label>
              <input value={form.contact_number} onChange={(e) => setField('contact_number', e.target.value)} className="w-full bg-chalk-warm border border-border-soft rounded-sm py-3 px-4 font-sans text-sm text-ink focus:border-mint/50 outline-none" />
            </div>
            <div>
              <label className="font-mono text-[11px] text-ink-faint uppercase tracking-[0.12em] mb-2 block">Hospital</label>
              <input value={form.hospital} onChange={(e) => setField('hospital', e.target.value)} className="w-full bg-chalk-warm border border-border-soft rounded-sm py-3 px-4 font-sans text-sm text-ink focus:border-mint/50 outline-none" />
            </div>
            <div>
              <label className="font-mono text-[11px] text-ink-faint uppercase tracking-[0.12em] mb-2 block">Qualification</label>
              <input value={form.qualification} onChange={(e) => setField('qualification', e.target.value)} className="w-full bg-chalk-warm border border-border-soft rounded-sm py-3 px-4 font-sans text-sm text-ink focus:border-mint/50 outline-none" />
            </div>
            <div>
              <label className="font-mono text-[11px] text-ink-faint uppercase tracking-[0.12em] mb-2 block">Speciality</label>
              <input value={form.speciality} onChange={(e) => setField('speciality', e.target.value)} className="w-full bg-chalk-warm border border-border-soft rounded-sm py-3 px-4 font-sans text-sm text-ink focus:border-mint/50 outline-none" />
            </div>
            <div>
              <label className="font-mono text-[11px] text-ink-faint uppercase tracking-[0.12em] mb-2 block">Country ID</label>
              <input value={form.country_id} onChange={(e) => setField('country_id', e.target.value)} className="w-full bg-chalk-warm border border-border-soft rounded-sm py-3 px-4 font-sans text-sm text-ink focus:border-mint/50 outline-none" />
            </div>
            <div>
              <label className="font-mono text-[11px] text-ink-faint uppercase tracking-[0.12em] mb-2 block">State</label>
              <input value={form.state} onChange={(e) => setField('state', e.target.value)} className="w-full bg-chalk-warm border border-border-soft rounded-sm py-3 px-4 font-sans text-sm text-ink focus:border-mint/50 outline-none" />
            </div>
            <div>
              <label className="font-mono text-[11px] text-ink-faint uppercase tracking-[0.12em] mb-2 block">City</label>
              <input value={form.city} onChange={(e) => setField('city', e.target.value)} className="w-full bg-chalk-warm border border-border-soft rounded-sm py-3 px-4 font-sans text-sm text-ink focus:border-mint/50 outline-none" />
            </div>
            <div>
              <label className="font-mono text-[11px] text-ink-faint uppercase tracking-[0.12em] mb-2 block">PIN Code</label>
              <input value={form.pin_code} onChange={(e) => setField('pin_code', e.target.value)} className="w-full bg-chalk-warm border border-border-soft rounded-sm py-3 px-4 font-sans text-sm text-ink focus:border-mint/50 outline-none" />
            </div>
            <div>
              <label className="font-mono text-[11px] text-ink-faint uppercase tracking-[0.12em] mb-2 block">Batch</label>
              <input value={data?.subscription || ''} disabled className="w-full bg-chalk-stone border border-border-soft rounded-sm py-3 px-4 font-sans text-sm text-ink-muted" />
            </div>
          </div>
          <button type="submit" disabled={saveMut.isPending} className="magnetic bg-slate text-chalk rounded-sm px-6 py-3 font-sans font-semibold text-sm hover:bg-slate-light transition-all disabled:opacity-60">
            {saveMut.isPending ? 'Saving...' : 'Save Changes'}
          </button>
        </form>
      </div>
    </div>
  );
}
