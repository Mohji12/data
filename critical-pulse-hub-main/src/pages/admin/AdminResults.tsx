import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/apiClient';
import { openAuthenticatedExport, openAuthenticatedPdf } from '@/lib/apiBase';
import { toast } from 'sonner';
import { Download, FileText, Search, User, CheckCircle, XCircle } from 'lucide-react';

export default function AdminResults() {
  const [selectedExam, setSelectedExam] = useState<number | null>(null);
  const [q, setQ] = useState('');
  const [sortBy, setSortBy] = useState<string>('id');
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');

  const { data: results, isLoading, error } = useQuery({
    queryKey: ['adminResults', selectedExam, q, sortBy, order],
    queryFn: () => {
      const p = new URLSearchParams();
      if (selectedExam) p.set('exam_id', String(selectedExam));
      if (q.trim()) p.set('q', q.trim());
      p.set('sort_by', sortBy);
      p.set('order', order);
      return apiClient(`/admin/quiz/results?${p.toString()}`);
    },
  });

  const { data: exams } = useQuery({
    queryKey: ['adminExamsList'],
    queryFn: () => apiClient('/admin/quiz/exams'),
  });

  const handleDownload = async (userExamId: number) => {
    try {
      await openAuthenticatedPdf(`/admin/quiz/results/${userExamId}/download.pdf`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'PDF download failed');
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
           <h1 className="font-display font-bold text-3xl text-slate text-center sm:text-left">Student Results</h1>
           <p className="font-mono text-[11px] text-ink-faint mt-1 uppercase tracking-wider">Monitor performance and export reports</p>
        </div>
        <button
          type="button"
          onClick={() => {
            const q = selectedExam ? `?exam_id=${selectedExam}` : '';
            void openAuthenticatedExport(`/admin/quiz/results/export.csv${q}`).catch((e) =>
              toast.error(e instanceof Error ? e.message : 'Export failed'),
            );
          }}
          className="magnetic bg-chalk border border-border-strong text-slate rounded-sm px-6 py-3 font-sans text-xs font-bold hover:bg-chalk-cool transition-all flex items-center justify-center gap-2 shadow-sm uppercase tracking-tighter cursor-pointer"
        >
          <Download size={14} /> Export CSV
        </button>
      </div>

      <div className="flex flex-col lg:flex-row gap-4 mb-8">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" size={14} />
          <input
            type="text"
            placeholder="Search email..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="w-full bg-white border border-border-soft rounded-sm py-2.5 pl-9 pr-4 font-sans text-sm outline-none focus:border-mint/50"
          />
        </div>
        <div className="flex items-center gap-2 flex-1">
          <select
            className="flex-1 bg-white border border-border-soft rounded-sm py-2.5 px-4 font-sans text-sm outline-none focus:border-mint/50"
            onChange={(e) => setSelectedExam(e.target.value ? parseInt(e.target.value) : null)}
            value={selectedExam || ''}
          >
            <option value="">Filter by Exam...</option>
            {exams?.map((e: any) => (
              <option key={e.id} value={e.id}>
                {e.title}
              </option>
            ))}
          </select>
        </div>
      </div>

      {isLoading && <div className="font-mono text-xs text-ink-faint py-12 text-center animate-pulse">Aggregating student metrics...</div>}
      {error && <div className="text-red-500 font-sans text-sm py-12 text-center">Error loading results.</div>}

      <div className="bg-white border border-border-soft rounded-sm shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="bg-chalk-cool border-b border-border-soft">
                {[
                  { id: 'user_email', label: 'Student' },
                  { id: 'exam_title', label: 'Mock Test' },
                  { id: 'attempt_no', label: 'Attempt' },
                  { id: 'marks', label: 'Score' },
                  { label: 'Status' },
                  { id: 'start_date', label: 'Attempted At' },
                  { label: 'Reports' },
                ].map((h) => (
                  <th
                    key={h.label}
                    onClick={() => 'id' in h && h.id && toggleSort(h.id)}
                    className={`font-mono text-[10px] text-ink-faint uppercase font-semibold text-left px-6 py-4 ${
                      h.label === 'Attempt' || h.label === 'Score' || h.label === 'Status' ? 'text-center' : ''
                    } ${'id' in h ? 'cursor-pointer hover:text-ink transition-colors' : ''}`}
                  >
                    {h.label}
                    {'id' in h && <SortIcon field={h.id!} />}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {results?.length === 0 && !isLoading && (
                <tr><td colSpan={7} className="text-center py-12 text-ink-muted font-sans text-sm">No exam attempts found.</td></tr>
              )}
              {results?.map((res: any) => (
                <tr key={res.user_exam_id} className="border-b border-border-soft last:border-0 hover:bg-slate-50 transition-colors">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-chalk-cool flex items-center justify-center text-ink-faint"><User size={14} /></div>
                        <span className="font-sans text-sm text-slate font-medium truncate max-w-[180px]" title={res.user_email}>{res.user_email}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className="font-sans text-xs text-ink-muted truncate max-w-[200px] block" title={res.exam_title}>{res.exam_title}</span>
                  </td>
                  <td className="px-6 py-4 text-center">
                    <span className="font-mono text-[11px] text-ink">{res.attempt_no || 1}</span>
                  </td>
                  <td className="px-6 py-4 text-center">
                    <span className="font-display font-black text-lg text-slate">{res.marks || 0}</span>
                  </td>
                  <td className="px-6 py-4 text-center">
                    <div className="flex items-center justify-center">
                        {res.is_finish_exam === '1' ? (
                            <div className="flex items-center gap-1.5 text-mint-dark font-mono text-[10px] font-bold uppercase">
                                <CheckCircle size={12} /> Done
                            </div>
                        ) : (
                            <div className="flex items-center gap-1.5 text-amber font-mono text-[10px] font-bold uppercase">
                                <XCircle size={12} /> In Progress
                            </div>
                        )}
                    </div>
                  </td>
                  <td className="px-6 py-4 font-mono text-[10px] text-ink-faint whitespace-nowrap">
                    {res.start_date ? new Date(res.start_date).toLocaleString() : 'N/A'}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button
                      type="button"
                      onClick={() => void handleDownload(res.user_exam_id)}
                      className="p-2.5 text-slate-light hover:text-slate bg-chalk hover:bg-chalk-cool border border-border-soft rounded-sm transition-all"
                      title="Download PDF Report"
                    >
                      <FileText size={16} />
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
