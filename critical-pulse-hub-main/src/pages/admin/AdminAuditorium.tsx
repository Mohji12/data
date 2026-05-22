import { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/apiClient';
import { useIsTechAdmin } from '@/store/authStore';

type BatchRow = { id: number; name: string; status?: string | null };

export default function AdminAuditorium() {
  const qc = useQueryClient();
  const isTech = useIsTechAdmin();
  const [link, setLink] = useState('');
  const [display, setDisplay] = useState('0');
  const [access, setAccess] = useState<string[]>([]);

  const { data, isLoading } = useQuery({
    queryKey: ['adminAuditorium'],
    queryFn: () => apiClient('/admin/auditorium'),
  });
  const { data: batches } = useQuery({
    queryKey: ['adminMiscBatches'],
    queryFn: () => apiClient('/admin/misc/batches') as Promise<BatchRow[]>,
  });
  const activeBatches = (batches || []).filter((b) => String(b.status ?? '1') === '1');

  useEffect(() => {
    if (!data) return;
    setLink(data.auditorium_link || '');
    setDisplay(data.display_auditorium_link || '0');
    setAccess(Array.isArray(data.access_auditorium_link) ? data.access_auditorium_link : []);
  }, [data]);

  const saveMut = useMutation({
    mutationFn: () =>
      apiClient('/admin/auditorium/save', {
        method: 'POST',
        body: JSON.stringify({
          auditorium_link: link,
          display_auditorium_link: display,
          access_auditorium_link: access,
        }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['adminAuditorium'] }),
  });

  return (
    <div className="p-6 lg:p-8">
      <h1 className="font-display font-bold text-3xl text-slate mb-2">Auditorium</h1>
      <p className="font-mono text-[11px] text-ink-faint mb-8 uppercase tracking-wider">Live embed + access by batch name</p>

      {isLoading && <p className="text-xs text-ink-faint animate-pulse">Loading…</p>}

      {!isTech && (
        <p className="text-sm text-amber mb-6 bg-amber-pale border border-amber/20 rounded-sm px-4 py-3">Only techadmin can save changes.</p>
      )}

      <div className="max-w-2xl bg-chalk border border-border-soft rounded-sm p-6 space-y-5">
        <div>
          <label className="font-mono text-[10px] text-ink-faint uppercase tracking-wider mb-2 block">Embed URL</label>
          <input
            value={link}
            onChange={(e) => setLink(e.target.value)}
            disabled={!isTech}
            className="w-full bg-chalk-warm border border-border-soft rounded-sm py-3 px-4 font-sans text-sm disabled:opacity-60"
          />
        </div>
        <div>
          <label className="font-mono text-[10px] text-ink-faint uppercase tracking-wider mb-2 block">Display auditorium link (0/1)</label>
          <select
            value={display}
            onChange={(e) => setDisplay(e.target.value)}
            disabled={!isTech}
            className="w-full bg-chalk-warm border border-border-soft rounded-sm py-3 px-4 font-sans text-sm disabled:opacity-60"
          >
            <option value="0">Hidden</option>
            <option value="1">Visible</option>
          </select>
        </div>
        <div>
          <label className="font-mono text-[10px] text-ink-faint uppercase tracking-wider mb-2 block">Access list (batches)</label>
          <select
            multiple
            value={access}
            onChange={(e) => setAccess(Array.from(e.target.selectedOptions).map((o) => o.value))}
            disabled={!isTech}
            className="w-full min-h-[140px] bg-chalk-warm border border-border-soft rounded-sm py-3 px-4 font-sans text-sm disabled:opacity-60"
          >
            {activeBatches.map((b) => (
              <option key={b.id} value={b.name}>
                {b.name}
              </option>
            ))}
          </select>
          <p className="text-[10px] text-ink-faint mt-1.5">Multi-select. Saved as batch names.</p>
        </div>
        {isTech && (
          <button
            type="button"
            disabled={saveMut.isPending}
            onClick={() => saveMut.mutate()}
            className="bg-mint text-slate rounded-sm px-6 py-3 font-sans font-semibold text-sm disabled:opacity-50"
          >
            Save
          </button>
        )}
      </div>
    </div>
  );
}
