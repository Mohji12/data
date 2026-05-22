import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/apiClient';
import { openAuthenticatedExport } from '@/lib/apiBase';
import { useIsTechAdmin } from '@/store/authStore';
import { toast } from 'sonner';

export default function AdminVideoQuestions() {
  const qc = useQueryClient();
  const isTech = useIsTechAdmin();
  const [sortBy, setSortBy] = useState<string>('id');
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');

  const { data: rows, isLoading, error } = useQuery({
    queryKey: ['adminVideoQuestions'],
    queryFn: () => apiClient('/admin/content/video-questions'),
  });

  const delMut = useMutation({
    mutationFn: (id: number) => apiClient(`/admin/content/video-questions/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['adminVideoQuestions'] }),
  });

  const delAllMut = useMutation({
    mutationFn: () => apiClient('/admin/content/video-questions/delete-all', { method: 'POST' }),
    onSuccess: () => {
      toast.success('All video questions removed');
      void qc.invalidateQueries({ queryKey: ['adminVideoQuestions'] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

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

  const sortedRows = [...(rows || [])].sort((a: any, b: any) => {
    const valA = a[sortBy];
    const valB = b[sortBy];
    if (typeof valA === 'string') {
      return order === 'asc' ? (valA || '').localeCompare(valB || '') : (valB || '').localeCompare(valA || '');
    }
    return order === 'asc' ? (valA || 0) - (valB || 0) : (valB || 0) - (valA || 0);
  });

  return (
    <div className="p-6 lg:p-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="font-display font-bold text-3xl text-slate">Video questions</h1>
          <p className="font-mono text-[11px] text-ink-faint mt-1 uppercase tracking-wider">Student questions on videos</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void openAuthenticatedExport('/admin/content/video-questions/export.csv')}
            className="magnetic bg-slate text-chalk rounded-sm px-4 py-2 font-sans text-xs font-semibold"
          >
            Export CSV
          </button>
          {isTech && (
            <button
              type="button"
              disabled={delAllMut.isPending || !rows?.length}
              onClick={() => {
                if (!window.confirm('Delete ALL video questions? This cannot be undone.')) return;
                delAllMut.mutate();
              }}
              className="rounded-sm border border-blush/50 text-blush px-4 py-2 font-sans text-xs font-semibold hover:bg-blush/5 disabled:opacity-40"
            >
              Delete all
            </button>
          )}
        </div>
      </div>

      {error && <p className="text-red-600 text-sm mb-4">{error instanceof Error ? error.message : 'Error'}</p>}
      {isLoading && <p className="text-xs text-ink-faint animate-pulse">Loading…</p>}

      <div className="overflow-x-auto border border-border-soft rounded-sm bg-chalk">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-chalk-cool">
              {[
                { id: 'id', label: 'ID' },
                { id: 'user_email', label: 'User' },
                { id: 'video_id', label: 'Video' },
                { id: 'question', label: 'Question' },
                { label: 'Actions' },
              ].map((h) => (
                <th
                  key={h.label}
                  onClick={() => 'id' in h && h.id && toggleSort(h.id)}
                  className={`text-left px-4 py-2 font-mono text-[10px] uppercase text-ink-faint ${
                    'id' in h ? 'cursor-pointer hover:text-ink transition-colors' : ''
                  } ${h.label === 'Actions' ? 'text-right' : ''}`}
                >
                  {h.label}
                  {'id' in h && <SortIcon field={h.id!} />}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows?.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-ink-muted">
                  No questions
                </td>
              </tr>
            )}
            {sortedRows?.map((q: any) => (
              <tr key={q.id} className="border-t border-border-soft align-top">
                <td className="px-4 py-2 font-mono text-xs text-ink-faint">{q.id}</td>
                <td className="px-4 py-2 font-mono text-xs">{q.user_email}</td>
                <td className="px-4 py-2 font-mono text-xs">{q.video_id}</td>
                <td className="px-4 py-2 font-sans text-ink-secondary max-w-md">{q.question}</td>
                <td className="px-4 py-2 text-right">
                  <button type="button" onClick={() => delMut.mutate(q.id)} className="text-xs text-blush font-semibold">
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
