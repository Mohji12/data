import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/apiClient';
import { useIsTechAdmin } from '@/store/authStore';
import { toast } from 'sonner';
import { Quote, Trash2, Loader2 } from 'lucide-react';

type TestimonialRow = {
  id: number;
  text: string;
  display_order: number;
  status?: string | null;
};

export default function AdminTestimonials() {
  const qc = useQueryClient();
  const isTech = useIsTechAdmin();
  const [text, setText] = useState('');
  const [displayOrder, setDisplayOrder] = useState('0');

  const { data: rows, isLoading, isError, error } = useQuery({
    queryKey: ['adminTestimonials'],
    queryFn: () => apiClient('/admin/misc/testimonials') as Promise<TestimonialRow[]>,
  });

  const createMut = useMutation({
    mutationFn: () =>
      apiClient('/admin/misc/testimonials', {
        method: 'POST',
        body: JSON.stringify({
          text: text.trim(),
          display_order: Math.max(0, Number(displayOrder) || 0),
          status: '1',
        }),
      }),
    onSuccess: () => {
      toast.success('Testimonial created');
      qc.invalidateQueries({ queryKey: ['adminTestimonials'] });
      setText('');
      setDisplayOrder('0');
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const delMut = useMutation({
    mutationFn: (id: number) => apiClient(`/admin/misc/testimonials/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      toast.success('Testimonial removed');
      void qc.invalidateQueries({ queryKey: ['adminTestimonials'] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const list = rows ?? [];
  const activeCount = list.filter((t) => String(t.status ?? '1') === '1').length;

  return (
    <div className="p-6 lg:p-8 min-w-0 max-w-full">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-6 mb-10">
        <div>
          <h1 className="font-display font-bold text-3xl text-slate text-center sm:text-left">Testimonials</h1>
          <p className="font-mono text-[11px] text-slate/55 mt-1.5 uppercase tracking-[0.14em] max-w-xl">
            Homepage quotes · order controls carousel sequence (matches PHP admin)
          </p>
        </div>
        {list.length > 0 && (
          <div className="flex flex-wrap gap-2 shrink-0">
            <span className="font-mono text-[10px] text-slate/70 border border-border-soft bg-chalk rounded-sm px-3 py-1.5">
              {list.length} total
            </span>
            <span className="font-mono text-[10px] text-mint border border-mint/25 bg-mint-pale rounded-sm px-3 py-1.5">
              {activeCount} active
            </span>
          </div>
        )}
      </div>

      {!isTech && (
        <div className="text-sm text-amber-900 mb-8 bg-amber-pale border border-amber/25 rounded-sm px-4 py-3 font-sans">
          Only <span className="font-semibold">tech admin</span> can add or delete testimonials.
        </div>
      )}

      {isTech && (
        <section className="mb-10 rounded-sm border border-border-soft bg-chalk shadow-sm overflow-hidden">
          <div className="border-b border-border-soft bg-chalk-cool/60 px-5 py-3 flex items-center gap-2">
            <div className="w-8 h-8 rounded-sm bg-mint/15 flex items-center justify-center shrink-0">
              <Quote className="w-4 h-4 text-mint" aria-hidden />
            </div>
            <div>
              <h2 className="font-display font-bold text-lg text-slate leading-tight">Add a testimonial</h2>
              <p className="font-mono text-[10px] text-slate/50 uppercase tracking-wider mt-0.5">Text &amp; display order</p>
            </div>
          </div>
          <div className="p-5 sm:p-6 space-y-5">
            <label className="block">
              <span className="font-mono text-[10px] text-slate/65 uppercase tracking-wider block mb-2">Quote text</span>
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={5}
                className="w-full bg-chalk-warm border border-border-soft rounded-sm py-3 px-3 font-sans text-sm text-slate leading-relaxed placeholder:text-slate/35 focus:outline-none focus:ring-2 focus:ring-mint/25 focus:border-mint/40 transition-shadow"
                placeholder="Enter the testimonial quote as it should appear on the homepage…"
              />
            </label>
            <div className="flex flex-col sm:flex-row sm:items-end gap-4 sm:gap-8">
              <label className="block sm:w-44 shrink-0">
                <span className="font-mono text-[10px] text-slate/65 uppercase tracking-wider block mb-2">Display order</span>
                <input
                  type="number"
                  min={0}
                  value={displayOrder}
                  onChange={(e) => setDisplayOrder(e.target.value)}
                  className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2.5 px-3 font-mono text-sm text-slate tabular-nums focus:outline-none focus:ring-2 focus:ring-mint/25 focus:border-mint/40"
                />
                <p className="text-[10px] text-slate/45 mt-1.5 font-sans">Lower numbers appear first.</p>
              </label>
              <div className="flex-1 sm:pb-0.5">
                <button
                  type="button"
                  disabled={!text.trim() || createMut.isPending}
                  onClick={() => createMut.mutate()}
                  className="magnetic w-full sm:w-auto min-w-[140px] bg-slate text-chalk rounded-sm px-6 py-2.5 font-sans text-sm font-semibold hover:bg-slate-light disabled:opacity-45 disabled:cursor-not-allowed inline-flex items-center justify-center gap-2 transition-colors"
                >
                  {createMut.isPending ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Saving…
                    </>
                  ) : (
                    'Save testimonial'
                  )}
                </button>
              </div>
            </div>
          </div>
        </section>
      )}

      {isLoading && (
        <div className="flex flex-col items-center justify-center py-20 gap-3">
          <Loader2 className="w-8 h-8 text-mint/60 animate-spin" />
          <p className="font-mono text-xs text-slate/45">Loading testimonials…</p>
        </div>
      )}

      {isError && (
        <div className="rounded-sm border border-blush/30 bg-blush/5 px-5 py-4 text-sm text-blush font-sans">
          {error instanceof Error ? error.message : 'Failed to load testimonials.'}
        </div>
      )}

      {!isLoading && !isError && list.length === 0 && (
        <div className="rounded-sm border border-dashed border-border-strong bg-chalk/80 px-8 py-16 text-center">
          <div className="w-14 h-14 mx-auto mb-4 rounded-full bg-chalk-cool flex items-center justify-center">
            <Quote className="w-7 h-7 text-slate/25" aria-hidden />
          </div>
          <p className="font-sans text-sm text-slate/70 max-w-sm mx-auto">
            No testimonials yet. {isTech ? 'Add your first quote above — it will show on the homepage when status is active.' : 'Ask a tech admin to add quotes.'}
          </p>
        </div>
      )}

      {!isLoading && !isError && list.length > 0 && (
        <section>
          <h2 className="font-mono text-[10px] text-slate/45 uppercase tracking-[0.12em] mb-4">Published quotes</h2>
          <ul className="grid gap-4">
            {list.map((t) => {
              const isActive = String(t.status ?? '1') === '1';
              return (
                <li
                  key={t.id}
                  className="group relative rounded-sm border border-border-soft bg-white hover:border-mint/25 hover:shadow-md transition-all duration-200 overflow-hidden"
                >
                  <div className="absolute left-0 top-0 bottom-0 w-1 bg-gradient-to-b from-mint/50 to-mint/20 opacity-80 group-hover:opacity-100 transition-opacity" aria-hidden />
                  <div className="pl-6 pr-4 py-5 sm:pl-7 sm:pr-6">
                    <div className="flex flex-col sm:flex-row sm:items-start gap-4 justify-between">
                      <blockquote className="min-w-0 flex-1">
                        <p className="font-sans text-[15px] sm:text-base text-slate/95 leading-relaxed whitespace-pre-wrap">
                          {t.text?.trim() || '—'}
                        </p>
                      </blockquote>
                      {isTech && (
                        <button
                          type="button"
                          onClick={() => {
                            if (!window.confirm('Delete this testimonial?')) return;
                            delMut.mutate(t.id);
                          }}
                          disabled={delMut.isPending}
                          className="shrink-0 inline-flex items-center gap-1.5 rounded-sm border border-blush/35 px-3 py-1.5 font-sans text-[11px] font-semibold text-blush hover:bg-blush/10 disabled:opacity-50 transition-colors self-start sm:self-start"
                        >
                          <Trash2 className="w-3.5 h-3.5" aria-hidden />
                          Delete
                        </button>
                      )}
                    </div>
                    <div className="flex flex-wrap items-center gap-2 mt-4 pt-4 border-t border-slate-100">
                      <span className="font-mono text-[10px] text-slate/50 border border-border-soft rounded-sm px-2 py-0.5">ID #{t.id}</span>
                      <span className="font-mono text-[10px] text-slate/50 border border-border-soft rounded-sm px-2 py-0.5">
                        Order {t.display_order ?? 0}
                      </span>
                      <span
                        className={
                          isActive
                            ? 'font-mono text-[10px] border border-mint/30 bg-mint-pale text-mint rounded-full px-2.5 py-0.5'
                            : 'font-mono text-[10px] border border-slate-200 bg-slate-50 text-slate/70 rounded-full px-2.5 py-0.5'
                        }
                      >
                        {isActive ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </div>
  );
}
