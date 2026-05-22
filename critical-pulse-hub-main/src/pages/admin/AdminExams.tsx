import { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/apiClient';
import { openAuthenticatedExport } from '@/lib/apiBase';
import { toast } from 'sonner';
import { Clock, HelpCircle, Plus, Pencil, Trash2, BarChart3, Download, List, X } from 'lucide-react';

type ExamRow = {
  id: number;
  title: string;
  description?: string | null;
  section_id: string;
  section_names?: string;
  batch?: string | null;
  total_questions?: number | null;
  timer_time?: number | null;
  start_date?: string | null;
  end_date?: string | null;
  status?: string | null;
  is_display_result?: string | null;
  is_display_correct_answer?: string | null;
};

type SectionOpt = { id: number; name: string; status?: string | null };
type BatchOpt = { id: number; name: string; status?: string | null };

type GraphAgg = Record<string, Record<string, number>>;

type GraphDetail = {
  labels: string[];
  counts: number[];
  percentages: number[];
  option_texts: Record<string, string>;
  total_answered: number;
  marking_description: string;
};

type PoolQ = { id: number; section_name: string; question: string; answer_type_label: string };

const emptyExam = () => ({
  title: '',
  description: '',
  sectionIds: new Set<number>(),
  batchNames: new Set<string>(),
  total_questions: 10,
  timer_time: 60,
  start_date: new Date().toISOString().slice(0, 10),
  end_date: new Date().toISOString().slice(0, 10),
  status: '1',
  is_display_result: '1',
  is_display_correct_answer: '0',
});

export default function AdminExams() {
  const qc = useQueryClient();
  const [graphExamId, setGraphExamId] = useState<number | ''>('');
  const [graphQuestionId, setGraphQuestionId] = useState<number | ''>('');
  const [q, setQ] = useState('');
  const [sortBy, setSortBy] = useState<string>('id');
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');
  const [modal, setModal] = useState<'add' | 'edit' | null>(null);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState(emptyExam());

  const { data: exams, isLoading, error } = useQuery({
    queryKey: ['adminExams', q, sortBy, order],
    queryFn: () => {
      const p = new URLSearchParams();
      if (q.trim()) p.set('q', q.trim());
      p.set('sort_by', sortBy);
      p.set('order', order);
      return apiClient(`/admin/quiz/exams?${p.toString()}`) as Promise<ExamRow[]>;
    },
  });

  const { data: sections } = useQuery({
    queryKey: ['adminQuizSections'],
    queryFn: () => apiClient('/admin/quiz/sections') as Promise<SectionOpt[]>,
  });

  const { data: batches } = useQuery({
    queryKey: ['adminMiscBatchesQuiz'],
    queryFn: () => apiClient('/admin/misc/batches') as Promise<BatchOpt[]>,
  });

  const { data: graphData, isLoading: graphLoading } = useQuery({
    queryKey: ['adminQuizQuestionGraph', graphExamId],
    queryFn: () => apiClient(`/admin/quiz/questions-graph?exam_id=${graphExamId}`) as Promise<GraphAgg>,
    enabled: graphExamId !== '' && Number(graphExamId) > 0,
  });

  const { data: poolQs } = useQuery({
    queryKey: ['adminExamPool', graphExamId],
    queryFn: () => apiClient(`/admin/quiz/exams/${graphExamId}/pool-questions`) as Promise<PoolQ[]>,
    enabled: graphExamId !== '' && Number(graphExamId) > 0,
  });

  const { data: graphDetail, isLoading: graphDetailLoading } = useQuery({
    queryKey: ['adminQuizGraphDetail', graphExamId, graphQuestionId],
    queryFn: () =>
      apiClient(`/admin/quiz/questions-graph-detail?exam_id=${graphExamId}&question_id=${graphQuestionId}`) as Promise<GraphDetail>,
    enabled:
      graphExamId !== '' &&
      graphQuestionId !== '' &&
      Number(graphExamId) > 0 &&
      Number(graphQuestionId) > 0,
  });

  const activeSections = useMemo(() => (sections || []).filter((s) => String(s.status ?? '1') === '1'), [sections]);
  const activeBatches = useMemo(() => (batches || []).filter((b) => String(b.status ?? '1') === '1'), [batches]);

  const invalidate = () => void qc.invalidateQueries({ queryKey: ['adminExams'] });

  const createMut = useMutation({
    mutationFn: () => {
      const sid = Array.from(form.sectionIds).sort((a, b) => a - b).join(',');
      const bat = Array.from(form.batchNames).join(',');
      return apiClient('/admin/quiz/exams', {
        method: 'POST',
        body: JSON.stringify({
          title: form.title.trim(),
          description: form.description.trim() || null,
          section_id: sid,
          batch: bat,
          total_questions: Number(form.total_questions),
          timer_time: Number(form.timer_time),
          start_date: `${form.start_date}T00:00:00`,
          end_date: `${form.end_date}T23:59:59`,
          status: form.status,
          is_display_result: form.is_display_result,
          is_display_correct_answer: form.is_display_correct_answer,
        }),
      });
    },
    onSuccess: () => {
      toast.success('Exam created');
      closeModal();
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const updateMut = useMutation({
    mutationFn: () => {
      if (editId == null) throw new Error('No exam id');
      const sid = Array.from(form.sectionIds).sort((a, b) => a - b).join(',');
      const bat = Array.from(form.batchNames).join(',');
      return apiClient(`/admin/quiz/exams/${editId}`, {
        method: 'PUT',
        body: JSON.stringify({
          title: form.title.trim(),
          description: form.description.trim() || null,
          section_id: sid,
          batch: bat,
          total_questions: Number(form.total_questions),
          timer_time: Number(form.timer_time),
          start_date: `${form.start_date}T00:00:00`,
          end_date: `${form.end_date}T23:59:59`,
          status: form.status,
          is_display_result: form.is_display_result,
          is_display_correct_answer: form.is_display_correct_answer,
        }),
      });
    },
    onSuccess: () => {
      toast.success('Exam updated');
      closeModal();
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => apiClient(`/admin/quiz/exams/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      toast.success('Exam deleted');
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const openAdd = () => {
    setForm(emptyExam());
    setEditId(null);
    setModal('add');
  };

  const openEdit = async (id: number) => {
    try {
      const e = (await apiClient(`/admin/quiz/exams/${id}`)) as {
        title: string;
        description?: string;
        section_id: string;
        batch: string;
        total_questions: number;
        timer_time: number;
        start_date: string | null;
        end_date: string | null;
        status: string;
        is_display_result: string;
        is_display_correct_answer: string;
      };
      const sids = new Set<number>();
      e.section_id.split(',').forEach((p) => {
        const t = p.trim();
        if (t && /^\d+$/.test(t)) sids.add(Number(t));
      });
      const bnames = new Set<string>();
      e.batch.split(',').forEach((p) => {
        const t = p.trim();
        if (t) bnames.add(t);
      });
      setForm({
        title: e.title || '',
        description: e.description || '',
        sectionIds: sids,
        batchNames: bnames,
        total_questions: e.total_questions ?? 10,
        timer_time: e.timer_time ?? 60,
        start_date: e.start_date?.slice(0, 10) || new Date().toISOString().slice(0, 10),
        end_date: e.end_date?.slice(0, 10) || new Date().toISOString().slice(0, 10),
        status: e.status || '1',
        is_display_result: e.is_display_result || '1',
        is_display_correct_answer: e.is_display_correct_answer || '0',
      });
      setEditId(id);
      setModal('edit');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to load exam');
    }
  };

  const closeModal = () => {
    setModal(null);
    setEditId(null);
    setForm(emptyExam());
  };

  const toggleSection = (id: number) => {
    setForm((f) => {
      const n = new Set(f.sectionIds);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return { ...f, sectionIds: n };
    });
  };

  const toggleBatch = (name: string) => {
    setForm((f) => {
      const n = new Set(f.batchNames);
      if (n.has(name)) n.delete(name);
      else n.add(name);
      return { ...f, batchNames: n };
    });
  };

  const graphRows =
    graphData &&
    Object.entries(graphData).map(([qid, answers]) => ({
      qid,
      answers: Object.entries(answers)
        .map(([k, v]) => `${k || '(empty)'}: ${v}`)
        .join(' · '),
    }));

  return (
    <div className="p-6 lg:p-8">
      {modal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 overflow-y-auto">
          <div className="bg-chalk border border-border-soft rounded-sm shadow-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto p-6 space-y-4 my-8">
            <div className="flex justify-between items-center">
              <h2 className="font-display font-bold text-xl text-slate">{modal === 'add' ? 'Add quiz exam' : 'Edit quiz exam'}</h2>
              <button type="button" className="p-1 rounded-sm hover:bg-chalk-cool" onClick={closeModal} aria-label="Close">
                <X size={20} />
              </button>
            </div>
            <p className="text-xs text-ink-muted">
              Matches PHP <span className="font-mono">Quiz_exam</span>: sections and batches are comma-separated lists; batch values are batch names.
            </p>
            <input
              type="text"
              placeholder="Exam title"
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
            />
            <textarea
              placeholder="Description (optional)"
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              rows={2}
              className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
            />
            <div className="grid sm:grid-cols-2 gap-3">
              <label className="block">
                <span className="font-mono text-xs text-ink-faint uppercase">Total questions</span>
                <input
                  type="number"
                  min={1}
                  value={form.total_questions}
                  onChange={(e) => setForm((f) => ({ ...f, total_questions: Number(e.target.value) }))}
                  className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
                />
              </label>
              <label className="block">
                <span className="font-mono text-xs text-ink-faint uppercase">Timer (minutes)</span>
                <input
                  type="number"
                  min={1}
                  value={form.timer_time}
                  onChange={(e) => setForm((f) => ({ ...f, timer_time: Number(e.target.value) }))}
                  className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
                />
              </label>
              <label className="block">
                <span className="font-mono text-xs text-ink-faint uppercase">Start date</span>
                <input
                  type="date"
                  value={form.start_date}
                  onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))}
                  className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
                />
              </label>
              <label className="block">
                <span className="font-mono text-xs text-ink-faint uppercase">End date</span>
                <input
                  type="date"
                  value={form.end_date}
                  onChange={(e) => setForm((f) => ({ ...f, end_date: e.target.value }))}
                  className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
                />
              </label>
            </div>
            <div>
              <span className="font-mono text-[10px] text-ink-faint uppercase block mb-2">Sections</span>
              <div className="flex flex-wrap gap-2 max-h-32 overflow-y-auto border border-border-soft rounded-sm p-2 bg-chalk-warm">
                {activeSections.map((s) => (
                  <label key={s.id} className="flex items-center gap-1.5 text-xs cursor-pointer">
                    <input type="checkbox" checked={form.sectionIds.has(s.id)} onChange={() => toggleSection(s.id)} />
                    {s.name}
                  </label>
                ))}
              </div>
            </div>
            <div>
              <span className="font-mono text-[10px] text-ink-faint uppercase block mb-2">Batches</span>
              <div className="flex flex-wrap gap-2 max-h-32 overflow-y-auto border border-border-soft rounded-sm p-2 bg-chalk-warm">
                {activeBatches.map((b) => (
                  <label key={b.id} className="flex items-center gap-1.5 text-xs cursor-pointer">
                    <input type="checkbox" checked={form.batchNames.has(b.name)} onChange={() => toggleBatch(b.name)} />
                    {b.name}
                  </label>
                ))}
              </div>
            </div>
            <div className="grid sm:grid-cols-3 gap-3">
              <label className="block">
                <span className="font-mono text-[10px] text-ink-faint uppercase">Status</span>
                <select
                  value={form.status}
                  onChange={(e) => setForm((f) => ({ ...f, status: e.target.value }))}
                  className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
                >
                  <option value="1">Active</option>
                  <option value="0">Deactive</option>
                </select>
              </label>
              <label className="block">
                <span className="font-mono text-[10px] text-ink-faint uppercase">Display result</span>
                <select
                  value={form.is_display_result}
                  onChange={(e) => setForm((f) => ({ ...f, is_display_result: e.target.value }))}
                  className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
                >
                  <option value="1">Yes</option>
                  <option value="0">No</option>
                </select>
              </label>
              <label className="block">
                <span className="font-mono text-[10px] text-ink-faint uppercase">Show correct answers</span>
                <select
                  value={form.is_display_correct_answer}
                  onChange={(e) => setForm((f) => ({ ...f, is_display_correct_answer: e.target.value }))}
                  className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
                >
                  <option value="1">Yes</option>
                  <option value="0">No</option>
                </select>
              </label>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" className="px-4 py-2 text-xs font-semibold border border-border-strong rounded-sm hover:bg-chalk-cool" onClick={closeModal}>
                Cancel
              </button>
              <button
                type="button"
                disabled={createMut.isPending || updateMut.isPending}
                className="magnetic bg-slate text-chalk rounded-sm px-4 py-2 font-sans text-xs font-semibold disabled:opacity-50"
                onClick={() => {
                  if (modal === 'add') createMut.mutate();
                  else if (modal === 'edit') updateMut.mutate();
                }}
              >
                {createMut.isPending || updateMut.isPending ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div className="flex-1">
          <h1 className="font-display font-bold text-3xl text-slate text-center sm:text-left">Exams</h1>
          <p className="font-mono text-[11px] text-ink-faint mt-1 uppercase tracking-wider">
            Quiz exams, batches, and sections (PHP quiz-exam parity)
          </p>
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search exam title..."
            className="bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm min-w-[240px]"
          />
          <button
            type="button"
            onClick={openAdd}
            className="magnetic bg-slate text-chalk rounded-sm px-6 py-3 font-sans text-sm font-semibold hover:bg-slate-light transition-all flex items-center justify-center gap-2"
          >
            <Plus size={16} /> Create exam
          </button>
        </div>
      </div>

      <div className="flex gap-4 mb-6 font-mono text-[10px] text-ink-faint uppercase tracking-wider items-center">
        <span>Sort by:</span>
        {[
          { id: 'id', label: 'ID' },
          { id: 'title', label: 'Title' },
          { id: 'start_date', label: 'Start Date' },
        ].map((s) => (
          <button
            key={s.id}
            onClick={() => {
              if (sortBy === s.id) setOrder(order === 'asc' ? 'desc' : 'asc');
              else {
                setSortBy(s.id);
                setOrder('desc');
              }
            }}
            className={`hover:text-slate transition-colors ${sortBy === s.id ? 'text-mint font-bold' : ''}`}
          >
            {s.label} {sortBy === s.id ? (order === 'asc' ? '↑' : '↓') : ''}
          </button>
        ))}
      </div>

      <section className="mb-10 bg-chalk border border-border-soft rounded-sm p-6 max-w-4xl">
        <div className="flex items-center gap-2 mb-3">
          <BarChart3 size={18} className="text-mint" />
          <h2 className="font-display font-bold text-lg text-slate">Question response stats</h2>
        </div>
        <p className="text-xs text-ink-muted mb-4">
          Raw counts by stored answer string. For PHP-style A–E percentages, pick a question below (same as admin questions graph).
        </p>
        <div className="grid sm:grid-cols-2 gap-4 mb-4">
          <select
            className="w-full bg-white border border-border-soft rounded-sm py-2.5 px-4 font-sans text-sm outline-none focus:border-mint/50"
            value={graphExamId === '' ? '' : String(graphExamId)}
            onChange={(e) => {
              setGraphExamId(e.target.value ? parseInt(e.target.value, 10) : '');
              setGraphQuestionId('');
            }}
          >
            <option value="">Select exam…</option>
            {exams?.map((e) => (
              <option key={e.id} value={e.id}>
                {e.title}
              </option>
            ))}
          </select>
          <select
            className="w-full bg-white border border-border-soft rounded-sm py-2.5 px-4 font-sans text-sm outline-none focus:border-mint/50"
            value={graphQuestionId === '' ? '' : String(graphQuestionId)}
            onChange={(e) => setGraphQuestionId(e.target.value ? parseInt(e.target.value, 10) : '')}
            disabled={!poolQs?.length}
          >
            <option value="">Select question for A–E graph…</option>
            {poolQs?.map((q) => (
              <option key={q.id} value={q.id}>
                #{q.id} — {q.answer_type_label}
              </option>
            ))}
          </select>
        </div>
        {graphDetailLoading && <p className="font-mono text-xs text-ink-faint animate-pulse">Loading graph detail…</p>}
        {graphDetail && graphQuestionId !== '' && (
          <div className="mb-6 overflow-x-auto border border-border-soft rounded-sm bg-white">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-chalk-cool border-b border-border-soft">
                  <th className="text-left px-3 py-2 font-mono text-[10px] text-ink-faint uppercase">Option</th>
                  <th className="text-left px-3 py-2 font-mono text-[10px] text-ink-faint uppercase">Label</th>
                  <th className="text-right px-3 py-2 font-mono text-[10px] text-ink-faint uppercase">Count</th>
                  <th className="text-right px-3 py-2 font-mono text-[10px] text-ink-faint uppercase">%</th>
                </tr>
              </thead>
              <tbody>
                {graphDetail.labels.map((lab, i) => (
                  <tr key={lab} className="border-b border-border-soft">
                    <td className="px-3 py-2 font-mono text-xs">{lab}</td>
                    <td className="px-3 py-2 text-xs text-ink-muted max-w-xs truncate" title={graphDetail.option_texts[lab]}>
                      {graphDetail.option_texts[lab] || '—'}
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-xs">{graphDetail.counts[i]}</td>
                    <td className="px-3 py-2 text-right font-mono text-xs">{graphDetail.percentages[i]}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-[10px] text-ink-faint px-3 py-2 font-mono">
              Answered: {graphDetail.total_answered} · {graphDetail.marking_description ? `Marking: ${graphDetail.marking_description}` : ''}
            </p>
          </div>
        )}
        {graphLoading && <p className="font-mono text-xs text-ink-faint animate-pulse">Loading aggregate…</p>}
        {graphExamId !== '' && !graphLoading && graphRows && (
          <div className="overflow-x-auto border border-border-soft rounded-sm bg-white max-h-80 overflow-y-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-chalk-cool border-b border-border-soft">
                  <th className="text-left px-3 py-2 font-mono text-[10px] text-ink-faint uppercase">Question ID</th>
                  <th className="text-left px-3 py-2 font-mono text-[10px] text-ink-faint uppercase">Answer string counts</th>
                </tr>
              </thead>
              <tbody>
                {graphRows.length === 0 && (
                  <tr>
                    <td colSpan={2} className="px-3 py-6 text-center text-ink-muted text-xs">
                      No attempts recorded for this exam.
                    </td>
                  </tr>
                )}
                {graphRows.map((row) => (
                  <tr key={row.qid} className="border-b border-border-soft align-top">
                    <td className="px-3 py-2 font-mono text-xs">{row.qid}</td>
                    <td className="px-3 py-2 font-mono text-[11px] text-ink-secondary">{row.answers || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {isLoading && (
        <div className="font-mono text-xs text-ink-faint py-12 text-center animate-pulse">Fetching exam catalogs...</div>
      )}
      {error && <div className="text-red-500 font-sans text-sm py-12 text-center">Error loading exams.</div>}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {exams?.map((exam) => (
          <div
            key={exam.id}
            className="bg-white border border-border-soft rounded-sm p-6 hover:border-mint/30 hover:shadow-md transition-all group flex flex-col justify-between"
          >
            <div>
              <div className="flex items-start justify-between mb-4">
                <div className={`w-10 h-10 rounded-sm flex items-center justify-center ${exam.status === '1' ? 'bg-mint/10' : 'bg-chalk-cool'}`}>
                  <HelpCircle size={18} className={exam.status === '1' ? 'text-mint' : 'text-ink-faint'} />
                </div>
              </div>

              <h3 className="font-display font-bold text-lg text-slate group-hover:text-mint transition-colors mb-2 truncate" title={exam.title}>
                {exam.title}
              </h3>
              <p className="font-mono text-[10px] text-ink-muted line-clamp-2 mb-2" title={exam.section_names || ''}>
                Sections: {exam.section_names || exam.section_id || '—'}
              </p>

              <div className="flex items-center gap-4 mb-4 flex-wrap">
                <div className="flex items-center gap-1.5 font-mono text-[10px] text-ink-muted">
                  <Clock size={12} /> {exam.timer_time || 0} MIN
                </div>
                <div className="font-mono text-[10px] text-ink-faint">•</div>
                <div className="font-mono text-[10px] text-ink-muted">Q {exam.total_questions ?? '—'}</div>
              </div>
            </div>

            <div className="pt-4 border-t border-slate-50 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-sans text-[11px] text-slate font-medium truncate max-w-[140px]" title={exam.batch || ''}>
                  {exam.batch || 'No batch'}
                </span>
                <span
                  className={`font-mono text-[9px] uppercase tracking-wider px-2 py-0.5 rounded-sm border ${
                    exam.status === '1' ? 'border-mint/30 text-mint' : 'border-border-strong text-ink-faint'
                  }`}
                >
                  {exam.status === '1' ? 'Active' : 'Draft'}
                </span>
              </div>
              <div className="flex flex-wrap gap-2">
                <Link
                  to={`/admin/quiz/questions?pool_exam_id=${exam.id}`}
                  className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-1 rounded-sm border border-sky-200 text-sky-800 hover:bg-sky-50"
                >
                  <List size={12} /> Pool
                </Link>
                <button
                  type="button"
                  onClick={() => void openAuthenticatedExport(`/admin/quiz/exams/${exam.id}/download-result`).catch((e) => toast.error(e.message))}
                  className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-1 rounded-sm border border-border-soft hover:bg-chalk-cool"
                >
                  <Download size={12} /> Results CSV
                </button>
                <button
                  type="button"
                  onClick={() => void openEdit(exam.id)}
                  className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-1 rounded-sm border border-mint/40 text-mint hover:bg-mint/10"
                >
                  <Pencil size={12} /> Edit
                </button>
                <button
                  type="button"
                  onClick={() => {
                    if (!window.confirm(`Delete exam #${exam.id}?`)) return;
                    deleteMut.mutate(exam.id);
                  }}
                  className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-1 rounded-sm border border-blush/40 text-blush hover:bg-blush/10"
                >
                  <Trash2 size={12} /> Delete
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
