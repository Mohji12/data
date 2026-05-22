import { useState, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/apiClient';
import { toast } from 'sonner';
import { Plus, Search, Filter, Trash2, Edit, X, ArrowLeft } from 'lucide-react';
import { resolvePublicUploadUrl } from '@/lib/apiBase';

type QuestionRow = {
  id: number;
  section_id: number;
  section_name?: string;
  marking_type_name?: string;
  question: string;
  answer?: string;
  answer_type?: string;
  answer_type_label?: string;
  status?: string;
};

type PoolRow = { id: number; section_name: string; question: string; answer_type_label: string; status?: string };

type QForm = {
  section_id: number;
  marking_type_id: number;
  question: string;
  answer: string;
  answer_type: string;
  option_a: string;
  option_b: string;
  option_c: string;
  option_d: string;
  option_e: string;
  question_image: string;
  is_mandatory_question: string;
  status: string;
};

const emptyForm = (): QForm => ({
  section_id: 0,
  marking_type_id: 0,
  question: '',
  answer: '',
  answer_type: 'R',
  option_a: '',
  option_b: '',
  option_c: '',
  option_d: '',
  option_e: '',
  question_image: '',
  is_mandatory_question: '0',
  status: '1',
});

export default function AdminQuestions() {
  const qc = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const poolExamId = searchParams.get('pool_exam_id') ? Number(searchParams.get('pool_exam_id')) : null;

  const [q, setQ] = useState('');
  const [selectedSection, setSelectedSection] = useState<number | null>(null);
  const [sortBy, setSortBy] = useState<string>('id');
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');
  const [modal, setModal] = useState<'add' | 'edit' | null>(null);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState<QForm>(emptyForm());

  const { data: questions, isLoading, error } = useQuery({
    queryKey: ['adminQuestions', selectedSection, q, sortBy, order],
    queryFn: () => {
      const p = new URLSearchParams();
      if (selectedSection) p.set('section_id', String(selectedSection));
      if (q.trim()) p.set('q', q.trim());
      p.set('sort_by', sortBy);
      p.set('order', order);
      return apiClient(`/admin/quiz/questions?${p.toString()}`) as Promise<QuestionRow[]>;
    },
  });

  const { data: sections } = useQuery({
    queryKey: ['adminSections'],
    queryFn: () => apiClient('/admin/quiz/sections') as Promise<{ id: number; name: string }[]>,
  });

  const { data: markingTypes } = useQuery({
    queryKey: ['adminMarkingTypes'],
    queryFn: () => apiClient('/admin/quiz/marking-types') as Promise<{ id: number; name: string }[]>,
  });

  const { data: poolExam } = useQuery({
    queryKey: ['adminExamForPool', poolExamId],
    queryFn: () => apiClient(`/admin/quiz/exams/${poolExamId}`) as Promise<{ title: string }>,
    enabled: poolExamId != null && poolExamId > 0,
  });

  const { data: poolQuestions } = useQuery({
    queryKey: ['adminPoolQuestions', poolExamId],
    queryFn: () => apiClient(`/admin/quiz/exams/${poolExamId}/pool-questions`) as Promise<PoolRow[]>,
    enabled: poolExamId != null && poolExamId > 0,
  });

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ['adminQuestions'] });
    void qc.invalidateQueries({ queryKey: ['adminPoolQuestions'] });
  };

  const uploadMut = useMutation({
    mutationFn: async (file: File) => {
      const fd = new FormData();
      fd.append('file', file);
      return apiClient('/admin/quiz/questions/upload-image', { method: 'POST', body: fd }) as Promise<{ filename: string }>;
    },
    onSuccess: (res) => {
      setForm((f) => ({ ...f, question_image: res.filename }));
      toast.success('Image uploaded');
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const createMut = useMutation({
    mutationFn: () =>
      apiClient('/admin/quiz/questions', {
        method: 'POST',
        body: JSON.stringify({
          section_id: form.section_id,
          marking_type_id: form.marking_type_id,
          question: form.question,
          answer: form.answer,
          answer_type: form.answer_type,
          option_a: form.option_a || null,
          option_b: form.option_b || null,
          option_c: form.option_c || null,
          option_d: form.option_d || null,
          option_e: form.option_e || null,
          question_image: form.question_image || null,
          is_mandatory_question: form.is_mandatory_question,
          status: form.status,
        }),
      }),
    onSuccess: () => {
      toast.success('Question created');
      closeModal();
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const updateMut = useMutation({
    mutationFn: () => {
      if (editId == null) throw new Error('No id');
      return apiClient(`/admin/quiz/questions/${editId}`, {
        method: 'PUT',
        body: JSON.stringify({
          section_id: form.section_id,
          marking_type_id: form.marking_type_id,
          question: form.question,
          answer: form.answer,
          answer_type: form.answer_type,
          option_a: form.option_a || null,
          option_b: form.option_b || null,
          option_c: form.option_c || null,
          option_d: form.option_d || null,
          option_e: form.option_e || null,
          question_image: form.question_image || null,
          is_mandatory_question: form.is_mandatory_question,
          status: form.status,
        }),
      });
    },
    onSuccess: () => {
      toast.success('Question updated');
      closeModal();
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => apiClient(`/admin/quiz/questions/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      toast.success('Deleted');
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const openAdd = () => {
    const firstSec = sections?.[0]?.id;
    const firstMt = markingTypes?.[0]?.id;
    setForm({
      ...emptyForm(),
      section_id: firstSec || 0,
      marking_type_id: firstMt || 0,
    });
    setEditId(null);
    setModal('add');
  };

  const openEdit = async (id: number) => {
    try {
      const row = (await apiClient(`/admin/quiz/questions/${id}`)) as QForm & { id: number };
      setForm({
        section_id: row.section_id,
        marking_type_id: row.marking_type_id,
        question: row.question || '',
        answer: row.answer || '',
        answer_type: row.answer_type || 'R',
        option_a: row.option_a || '',
        option_b: row.option_b || '',
        option_c: row.option_c || '',
        option_d: row.option_d || '',
        option_e: row.option_e || '',
        question_image: row.question_image || '',
        is_mandatory_question: row.is_mandatory_question || '0',
        status: row.status || '1',
      });
      setEditId(id);
      setModal('edit');
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Load failed');
    }
  };

  const closeModal = () => {
    setModal(null);
    setEditId(null);
    setForm(emptyForm());
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

  const clearPool = () => {
    searchParams.delete('pool_exam_id');
    setSearchParams(searchParams);
  };

  return (
    <div className="p-6 lg:p-8">
      {modal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 overflow-y-auto">
          <div className="bg-chalk border border-border-soft rounded-sm shadow-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto p-6 space-y-3 my-8">
            <div className="flex justify-between items-center">
              <h2 className="font-display font-bold text-xl text-slate">{modal === 'add' ? 'New question' : 'Edit question'}</h2>
              <button type="button" className="p-1 rounded-sm hover:bg-chalk-cool" onClick={closeModal} aria-label="Close">
                <X size={20} />
              </button>
            </div>
            <p className="text-xs text-ink-muted">PHP parity: marking type, answer type, options for Radio/Checkbox, mandatory flag.</p>
            <div className="grid sm:grid-cols-2 gap-3">
              <label className="block">
                <span className="font-mono text-[10px] text-ink-faint uppercase">Section</span>
                <select
                  value={form.section_id}
                  onChange={(e) => setForm((f) => ({ ...f, section_id: Number(e.target.value) }))}
                  className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
                >
                  {sections?.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="font-mono text-[10px] text-ink-faint uppercase">Marking type</span>
                <select
                  value={form.marking_type_id}
                  onChange={(e) => setForm((f) => ({ ...f, marking_type_id: Number(e.target.value) }))}
                  className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
                >
                  {markingTypes?.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label className="block">
              <span className="font-mono text-[10px] text-ink-faint uppercase">Question (HTML ok)</span>
              <textarea
                value={form.question}
                onChange={(e) => setForm((f) => ({ ...f, question: e.target.value }))}
                rows={4}
                className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm font-mono text-xs"
              />
            </label>
            <div className="grid sm:grid-cols-2 gap-3">
              <label className="block">
                <span className="font-mono text-[10px] text-ink-faint uppercase">Answer type</span>
                <select
                  value={form.answer_type}
                  onChange={(e) => setForm((f) => ({ ...f, answer_type: e.target.value }))}
                  className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
                >
                  <option value="R">Radio (R)</option>
                  <option value="C">Checkbox (C)</option>
                  <option value="MTF">MTF</option>
                </select>
              </label>
              <label className="block">
                <span className="font-mono text-[10px] text-ink-faint uppercase">Correct answer</span>
                <input
                  value={form.answer}
                  onChange={(e) => setForm((f) => ({ ...f, answer: e.target.value }))}
                  className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
                  placeholder="e.g. A or A,B"
                />
              </label>
            </div>
            {['option_a', 'option_b', 'option_c', 'option_d', 'option_e'].map((k) => (
              <label key={k} className="block">
                <span className="font-mono text-[10px] text-ink-faint uppercase">{k.replace('option_', 'Option ').toUpperCase()}</span>
                <input
                  value={form[k as keyof QForm] as string}
                  onChange={(e) => setForm((f) => ({ ...f, [k]: e.target.value }))}
                  className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
                />
              </label>
            ))}
            <div className="grid sm:grid-cols-2 gap-3">
              <label className="block">
                <span className="font-mono text-[10px] text-ink-faint uppercase">Mandatory</span>
                <select
                  value={form.is_mandatory_question}
                  onChange={(e) => setForm((f) => ({ ...f, is_mandatory_question: e.target.value }))}
                  className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
                >
                  <option value="0">No</option>
                  <option value="1">Yes</option>
                </select>
              </label>
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
            </div>
            <div>
              <span className="font-mono text-xs text-ink-faint uppercase block mb-1">Question image</span>
              <div className="flex items-start gap-4 p-3 border border-border-soft rounded-sm bg-chalk-warm">
                {form.question_image && (
                   <div className="w-20 h-20 bg-chalk border border-border-soft rounded-sm overflow-hidden flex-shrink-0 flex items-center justify-center">
                      <img 
                        src={resolvePublicUploadUrl(`/upload/quiz/questions/${form.question_image}`) || ''} 
                        alt="Question" 
                        className="w-full h-full object-contain"
                        onError={(e) => (e.currentTarget.style.display = 'none')}
                      />
                   </div>
                )}
                <div className="flex-1">
                  <input
                    type="file"
                    id="question_image_input"
                    accept="image/jpeg,image/png,image/webp"
                    disabled={uploadMut.isPending}
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) uploadMut.mutate(file);
                      e.target.value = '';
                    }}
                    className="hidden"
                  />
                  <label 
                    htmlFor="question_image_input"
                    className="inline-block px-3 py-1.5 rounded-sm bg-slate text-chalk border border-slate font-sans text-xs font-bold cursor-pointer hover:bg-slate-light"
                  >
                    {uploadMut.isPending ? 'Uploading...' : 'Select Image'}
                  </label>
                  {form.question_image && (
                    <p className="font-mono text-[10px] text-ink-muted mt-2 break-all font-bold">File: {form.question_image}</p>
                  )}
                </div>
              </div>
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
                  else updateMut.mutate();
                }}
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="font-display font-bold text-3xl text-slate text-center sm:text-left">Question Bank</h1>
          <p className="font-mono text-[11px] text-ink-faint mt-1 uppercase tracking-wider">Quiz questions (PHP quiz-questions parity)</p>
        </div>
        <button
          type="button"
          onClick={openAdd}
          className="magnetic bg-slate text-chalk rounded-sm px-6 py-3 font-sans text-sm font-semibold hover:bg-slate-light transition-all flex items-center justify-center gap-2"
        >
          <Plus size={16} /> New Question
        </button>
      </div>

      {poolExamId != null && poolExamId > 0 && (
        <div className="mb-6 bg-sky-50 border border-sky-200 rounded-sm p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="font-mono text-[10px] text-sky-900 uppercase">Exam question pool</div>
            <div className="font-sans text-sm font-semibold text-slate">{poolExam?.title || `Exam #${poolExamId}`}</div>
            <p className="text-xs text-ink-muted mt-1">Same pool as PHP “View Questions” for this exam.</p>
          </div>
          <button
            type="button"
            onClick={clearPool}
            className="inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-2 rounded-sm border border-sky-300 text-sky-900 hover:bg-white"
          >
            <ArrowLeft size={14} /> All questions
          </button>
        </div>
      )}

      {poolExamId != null && poolExamId > 0 && (
        <div className="mb-10 bg-white border border-border-soft rounded-sm overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-chalk-cool border-b border-border-soft">
                <th className="text-left px-4 py-2 font-mono text-[10px] text-ink-faint uppercase">ID</th>
                <th className="text-left px-4 py-2 font-mono text-[10px] text-ink-faint uppercase">Section</th>
                <th className="text-left px-4 py-2 font-mono text-[10px] text-ink-faint uppercase">Type</th>
                <th className="text-left px-4 py-2 font-mono text-[10px] text-ink-faint uppercase">Preview</th>
              </tr>
            </thead>
            <tbody>
              {(poolQuestions || []).map((p) => (
                <tr key={p.id} className="border-b border-border-soft">
                  <td className="px-4 py-2 font-mono text-xs">#{p.id}</td>
                  <td className="px-4 py-2 text-xs">{p.section_name}</td>
                  <td className="px-4 py-2 font-mono text-[10px]">{p.answer_type_label}</td>
                  <td className="px-4 py-2 text-xs line-clamp-2 max-w-md" dangerouslySetInnerHTML={{ __html: p.question?.slice(0, 120) || '' }} />
                </tr>
              ))}
            </tbody>
          </table>
          {!poolQuestions?.length && <div className="p-8 text-center text-ink-muted text-sm">No questions in pool for this exam.</div>}
        </div>
      )}

      <div className="flex flex-col lg:flex-row gap-4 mb-8">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" size={14} />
          <input
            type="text"
            placeholder="Search question text..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="w-full bg-white border border-border-soft rounded-sm py-2.5 pl-9 pr-4 font-sans text-sm outline-none focus:border-mint/50"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="text-ink-faint" size={14} />
          <select
            className="bg-white border border-border-soft rounded-sm py-2.5 px-4 font-sans text-sm outline-none focus:border-mint/50"
            onChange={(e) => setSelectedSection(e.target.value ? parseInt(e.target.value) : null)}
            value={selectedSection || ''}
          >
            <option value="">All Sections</option>
            {sections?.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} (ID #{s.id})
              </option>
            ))}
          </select>
        </div>
      </div>

      {isLoading && <div className="font-mono text-xs text-ink-faint py-12 text-center animate-pulse">Scanning question database...</div>}
      {error && <div className="text-red-500 font-sans text-sm py-12 text-center">Error loading question bank.</div>}

      <div className="bg-white border border-border-soft rounded-sm shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="bg-chalk-cool border-b border-border-soft">
                {[
                  { id: 'id', label: 'ID' },
                  { label: 'Section' },
                  { label: 'Marking' },
                  { id: 'question', label: 'Question Text' },
                  { label: 'Type' },
                  { label: 'Status' },
                  { label: 'Actions' },
                ].map((h) => (
                  <th
                    key={h.label}
                    onClick={() => 'id' in h && h.id && toggleSort(h.id)}
                    className={`font-mono text-[10px] text-ink-faint uppercase font-semibold text-left px-6 py-4 ${
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
              {(questions || []).length === 0 && !isLoading && (
                <tr>
                  <td colSpan={7} className="text-center py-12 text-ink-muted font-sans text-sm">
                    No questions found for the selected filter.
                  </td>
                </tr>
              )}
              {(questions || []).map((qrow) => (
                <tr key={qrow.id} className="border-b border-border-soft last:border-0 hover:bg-slate-50 transition-colors">
                  <td className="px-6 py-4 font-mono text-[11px] text-ink-faint">#{qrow.id}</td>
                  <td className="px-6 py-4 font-mono text-[10px] text-ink-muted max-w-[120px]">{qrow.section_name || '—'}</td>
                  <td className="px-6 py-4 font-mono text-[10px] text-ink-muted max-w-[100px] truncate" title={qrow.marking_type_name}>
                    {qrow.marking_type_name || '—'}
                  </td>
                  <td className="px-6 py-4">
                    <div className="font-sans text-sm text-slate line-clamp-2 max-w-[500px] prose-sm" dangerouslySetInnerHTML={{ __html: qrow.question }} />
                  </td>
                  <td className="px-6 py-4 font-mono text-[11px] text-ink-muted">{qrow.answer_type_label || qrow.answer_type}</td>
                  <td className="px-6 py-4">
                    <span
                      className={`font-mono text-[9px] uppercase tracking-wider px-2 py-0.5 rounded-sm border ${
                        qrow.status === '1' ? 'border-mint/30 text-mint' : 'border-border-strong text-ink-faint'
                      }`}
                    >
                      {qrow.status === '1' ? 'Live' : 'Hidden'}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex items-center justify-end gap-2 text-ink-faint">
                      <button
                        type="button"
                        className="p-2 hover:text-slate transition-colors hover:bg-chalk rounded-sm"
                        onClick={() => void openEdit(qrow.id)}
                      >
                        <Edit size={14} />
                      </button>
                      <button
                        type="button"
                        className="p-2 hover:text-cherry transition-colors hover:bg-chalk rounded-sm"
                        onClick={() => {
                          if (!window.confirm(`Delete question #${qrow.id}?`)) return;
                          deleteMut.mutate(qrow.id);
                        }}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
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
