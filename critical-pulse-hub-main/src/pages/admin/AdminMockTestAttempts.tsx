import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { apiClient } from '@/lib/apiClient';

type MockTestAttemptLimits = {
  default_max_attempts: number;
  batch_overrides: Record<string, number>;
};

type BatchOpt = { id: number; name: string; status?: string | null };

function clampAttempts(n: number): number {
  return Math.max(1, Math.min(50, n));
}

export default function AdminMockTestAttempts() {
  const qc = useQueryClient();
  const [defaultAttempts, setDefaultAttempts] = useState('2');
  const [batchName, setBatchName] = useState('');
  const [batchAttempts, setBatchAttempts] = useState('3');

  const { data: limits, isLoading } = useQuery({
    queryKey: ['adminMockTestAttemptLimits'],
    queryFn: () => apiClient('/admin/quiz/attempt-limits') as Promise<MockTestAttemptLimits>,
  });

  const { data: batches } = useQuery({
    queryKey: ['adminMiscBatches'],
    queryFn: () => apiClient('/admin/misc/batches') as Promise<BatchOpt[]>,
  });

  const activeBatches = useMemo(
    () => (batches || []).filter((b) => String(b.status ?? '1') === '1'),
    [batches],
  );

  useEffect(() => {
    if (limits) setDefaultAttempts(String(limits.default_max_attempts));
  }, [limits]);

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ['adminMockTestAttemptLimits'] });
    void qc.invalidateQueries({ queryKey: ['adminUsers'] });
  };

  const saveDefaultMut = useMutation({
    mutationFn: async () => {
      const defaultNum = clampAttempts(parseInt(defaultAttempts, 10) || 2);
      return apiClient('/admin/quiz/attempt-limits', {
        method: 'PUT',
        body: JSON.stringify({
          default_max_attempts: defaultNum,
          batch_overrides: limits?.batch_overrides || {},
        }),
      }) as Promise<MockTestAttemptLimits>;
    },
    onSuccess: (saved) => {
      qc.setQueryData(['adminMockTestAttemptLimits'], saved);
      setDefaultAttempts(String(saved.default_max_attempts));
      toast.success('Default attempt limit saved');
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const saveBatchMut = useMutation({
    mutationFn: async () => {
      const name = batchName.trim();
      if (!name) throw new Error('Select a batch');
      const val = clampAttempts(parseInt(batchAttempts, 10) || 2);
      const nextOverrides = { ...(limits?.batch_overrides || {}), [name]: val };
      const defaultNum = clampAttempts(parseInt(defaultAttempts, 10) || limits?.default_max_attempts || 2);
      return apiClient('/admin/quiz/attempt-limits', {
        method: 'PUT',
        body: JSON.stringify({
          default_max_attempts: defaultNum,
          batch_overrides: nextOverrides,
        }),
      }) as Promise<MockTestAttemptLimits>;
    },
    onSuccess: (saved) => {
      qc.setQueryData(['adminMockTestAttemptLimits'], saved);
      toast.success(`Batch override saved for ${batchName.trim()}`);
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const removeBatchMut = useMutation({
    mutationFn: async (name: string) => {
      const nextOverrides = { ...(limits?.batch_overrides || {}) };
      delete nextOverrides[name];
      const defaultNum = clampAttempts(parseInt(defaultAttempts, 10) || limits?.default_max_attempts || 2);
      return apiClient('/admin/quiz/attempt-limits', {
        method: 'PUT',
        body: JSON.stringify({
          default_max_attempts: defaultNum,
          batch_overrides: nextOverrides,
        }),
      }) as Promise<MockTestAttemptLimits>;
    },
    onSuccess: (saved) => {
      qc.setQueryData(['adminMockTestAttemptLimits'], saved);
      toast.success('Batch override removed');
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const batchRows = Object.entries(limits?.batch_overrides || {}).map(([name, max]) => ({ name, max }));

  return (
    <div className="p-6 lg:p-8">
      <h1 className="font-display font-bold text-3xl text-slate mb-2">Mock test attempt limits</h1>
      <p className="font-sans text-sm text-ink-muted mb-8 max-w-2xl">
        Default is 2 attempts per mock test. Set a higher limit for an entire batch (matched by user subscription name)
        or override a single user on the{' '}
        <Link to="/admin/users" className="text-mint hover:underline">
          Users
        </Link>{' '}
        page. Priority: user override → batch override → default.
      </p>

      {isLoading && <p className="font-mono text-xs text-ink-faint animate-pulse">Loading…</p>}

      <div className="grid gap-8 lg:grid-cols-2 max-w-5xl">
        <section className="bg-chalk border border-border-soft rounded-sm p-6 space-y-4">
          <h2 className="font-mono text-[10px] text-mint uppercase tracking-wider">Site default</h2>
          <label className="block font-sans text-sm text-ink-secondary">
            Max attempts for all users (unless batch/user override applies)
            <input
              type="number"
              min={1}
              max={50}
              value={defaultAttempts}
              onChange={(e) => setDefaultAttempts(e.target.value)}
              className="mt-2 w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-mono text-sm"
            />
          </label>
          <button
            type="button"
            disabled={saveDefaultMut.isPending}
            onClick={() => saveDefaultMut.mutate()}
            className="bg-slate text-chalk rounded-sm px-4 py-2 font-sans text-sm font-semibold disabled:opacity-50"
          >
            {saveDefaultMut.isPending ? 'Saving…' : 'Save default'}
          </button>
        </section>

        <section className="bg-chalk border border-border-soft rounded-sm p-6 space-y-4">
          <h2 className="font-mono text-[10px] text-mint uppercase tracking-wider">Batch override</h2>
          <label className="block font-sans text-sm text-ink-secondary">
            Batch
            <select
              value={batchName}
              onChange={(e) => setBatchName(e.target.value)}
              className="mt-2 w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm"
            >
              <option value="">Select batch…</option>
              {activeBatches.map((b) => (
                <option key={b.id} value={b.name}>
                  {b.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block font-sans text-sm text-ink-secondary">
            Max attempts
            <input
              type="number"
              min={1}
              max={50}
              value={batchAttempts}
              onChange={(e) => setBatchAttempts(e.target.value)}
              className="mt-2 w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-mono text-sm"
            />
          </label>
          <button
            type="button"
            disabled={saveBatchMut.isPending || !batchName.trim()}
            onClick={() => saveBatchMut.mutate()}
            className="bg-slate text-chalk rounded-sm px-4 py-2 font-sans text-sm font-semibold disabled:opacity-50"
          >
            {saveBatchMut.isPending ? 'Saving…' : 'Add / update batch'}
          </button>
        </section>
      </div>

      <div className="mt-10 max-w-3xl">
        <h2 className="font-mono text-[10px] text-ink-faint uppercase tracking-wider mb-3">Active batch overrides</h2>
        <div className="overflow-x-auto border border-border-soft rounded-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-chalk-cool">
                <th className="text-left px-4 py-2 font-mono text-[10px] uppercase text-ink-faint">Batch</th>
                <th className="text-left px-4 py-2 font-mono text-[10px] uppercase text-ink-faint">Max attempts</th>
                <th className="text-right px-4 py-2 font-mono text-[10px] uppercase text-ink-faint">Actions</th>
              </tr>
            </thead>
            <tbody>
              {batchRows.length === 0 && (
                <tr>
                  <td colSpan={3} className="px-4 py-8 text-center font-sans text-sm text-ink-muted">
                    No batch overrides yet.
                  </td>
                </tr>
              )}
              {batchRows.map((row) => (
                <tr key={row.name} className="border-t border-border-soft">
                  <td className="px-4 py-2 font-sans">{row.name}</td>
                  <td className="px-4 py-2 font-mono text-xs">{row.max}</td>
                  <td className="px-4 py-2 text-right">
                    <button
                      type="button"
                      disabled={removeBatchMut.isPending}
                      onClick={() => {
                        if (!window.confirm(`Remove override for ${row.name}?`)) return;
                        removeBatchMut.mutate(row.name);
                      }}
                      className="text-xs text-blush font-semibold disabled:opacity-50"
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
