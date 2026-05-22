import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/apiClient';

export default function AdminMarkingTypes() {
  const qc = useQueryClient();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [negative, setNegative] = useState(0);

  const { data: rows, isLoading } = useQuery({
    queryKey: ['adminMarkingTypes'],
    queryFn: () => apiClient('/admin/quiz/marking-types'),
  });

  const createMut = useMutation({
    mutationFn: () =>
      apiClient('/admin/quiz/marking-types', {
        method: 'POST',
        body: JSON.stringify({ name, description: description || null, negative_mark: negative, status: '1' }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['adminMarkingTypes'] });
      setName('');
      setDescription('');
      setNegative(0);
    },
  });

  const delMut = useMutation({
    mutationFn: (id: number) => apiClient(`/admin/quiz/marking-types/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['adminMarkingTypes'] }),
  });

  return (
    <div className="p-6 lg:p-8">
      <h1 className="font-display font-bold text-3xl text-slate mb-2">Marking types</h1>
      <p className="font-mono text-[11px] text-ink-faint mb-8 uppercase tracking-wider">Quiz scoring rules</p>

      <div className="max-w-xl bg-chalk border border-border-soft rounded-sm p-6 mb-8 space-y-4">
        <div className="font-mono text-[10px] text-mint uppercase tracking-wider">New marking type</div>
        <input
          placeholder="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm"
        />
        <input
          placeholder="Description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm"
        />
        <input
          type="number"
          step="0.01"
          placeholder="Negative mark"
          value={negative}
          onChange={(e) => setNegative(Number(e.target.value))}
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
              <th className="text-left px-4 py-2 font-mono text-[10px] uppercase text-ink-faint">Neg</th>
              <th className="text-right px-4 py-2 font-mono text-[10px] uppercase text-ink-faint">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows?.map((m: any) => (
              <tr key={m.id} className="border-t border-border-soft">
                <td className="px-4 py-2 font-mono text-xs">{m.id}</td>
                <td className="px-4 py-2">{m.name}</td>
                <td className="px-4 py-2 font-mono text-xs">{m.negative_mark}</td>
                <td className="px-4 py-2 text-right">
                  <button type="button" onClick={() => delMut.mutate(m.id)} className="text-xs text-blush font-semibold">
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
