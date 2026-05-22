import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/apiClient';

export default function AdminQuizSections() {
  const qc = useQueryClient();
  const [name, setName] = useState('');
  const [order, setOrder] = useState(0);

  const { data: sections, isLoading } = useQuery({
    queryKey: ['adminQuizSections'],
    queryFn: () => apiClient('/admin/quiz/sections'),
  });

  const createMut = useMutation({
    mutationFn: () =>
      apiClient('/admin/quiz/sections', {
        method: 'POST',
        body: JSON.stringify({
          name,
          display_order: order,
          status: '1',
        }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['adminQuizSections'] });
      setName('');
      setOrder(0);
    },
  });

  const delMut = useMutation({
    mutationFn: (id: number) => apiClient(`/admin/quiz/sections/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['adminQuizSections'] }),
  });

  return (
    <div className="p-6 lg:p-8">
      <h1 className="font-display font-bold text-3xl text-slate mb-2">Quiz sections</h1>
      <p className="font-mono text-[11px] text-slate/55 mb-8 uppercase tracking-wider max-w-xl">
        Section bank (shared). Assign to exams via each exam’s section list (PHP parity).
      </p>

      <div className="max-w-xl bg-chalk border border-border-soft rounded-sm p-6 mb-8 space-y-4">
        <div className="font-mono text-[10px] text-mint uppercase tracking-wider">New section</div>
        <input
          placeholder="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm"
        />
        <input
          type="number"
          placeholder="Display order"
          value={order}
          onChange={(e) => setOrder(Number(e.target.value))}
          className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm"
        />
        <button
          type="button"
          disabled={!name.trim() || createMut.isPending}
          onClick={() => createMut.mutate()}
          className="bg-slate text-chalk rounded-sm px-4 py-2 font-sans text-sm font-semibold disabled:opacity-50"
        >
          Create
        </button>
      </div>

      {isLoading && <p className="text-xs text-ink-faint animate-pulse">Loading…</p>}
      <div className="overflow-x-auto border border-border-soft rounded-sm">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-chalk-cool">
              <th className="text-left px-4 py-2 font-mono text-[10px] uppercase text-ink-faint">ID</th>
              <th className="text-left px-4 py-2 font-mono text-[10px] uppercase text-ink-faint">Name</th>
              <th className="text-left px-4 py-2 font-mono text-[10px] uppercase text-ink-faint">Order</th>
              <th className="text-right px-4 py-2 font-mono text-[10px] uppercase text-ink-faint">Actions</th>
            </tr>
          </thead>
          <tbody>
            {sections?.map((s: any) => (
              <tr key={s.id} className="border-t border-border-soft">
                <td className="px-4 py-2 font-mono text-xs">{s.id}</td>
                <td className="px-4 py-2">{s.name}</td>
                <td className="px-4 py-2 font-mono text-xs">{s.display_order}</td>
                <td className="px-4 py-2 text-right">
                  <button type="button" onClick={() => delMut.mutate(s.id)} className="text-xs text-blush font-semibold">
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
