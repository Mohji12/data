import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { apiClient } from '@/lib/apiClient';
import { useIsTechAdmin } from '@/store/authStore';
import AdminMailNav from './AdminMailNav';
import type { MailTemplate } from './mailTypes';

export default function AdminMailTemplates() {
  const isTech = useIsTechAdmin();
  const qc = useQueryClient();
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['adminMailTemplates'],
    queryFn: () => apiClient('/admin/mail/templates') as Promise<MailTemplate[]>,
  });

  const archiveMut = useMutation({
    mutationFn: (id: number) => apiClient(`/admin/mail/templates/${id}/archive`, { method: 'POST' }),
    onSuccess: () => {
      toast.success('Template archived');
      void qc.invalidateQueries({ queryKey: ['adminMailTemplates'] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const dupMut = useMutation({
    mutationFn: (id: number) => apiClient(`/admin/mail/templates/${id}/duplicate`, { method: 'POST' }),
    onSuccess: () => {
      toast.success('Template duplicated');
      void qc.invalidateQueries({ queryKey: ['adminMailTemplates'] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const list = data ?? [];

  return (
    <div className="p-6 lg:p-8 min-w-0 max-w-full">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-6 mb-6">
        <div>
          <h1 className="font-display font-bold text-3xl text-slate">Templates</h1>
          <p className="font-mono text-[11px] text-slate/55 mt-1.5 uppercase tracking-[0.14em]">
            Reusable campaign layouts · variables {'{{name}} {{email}} {{batch}}'}
          </p>
        </div>
        {isTech && (
          <Link
            to="/admin/mail/templates/new"
            className="font-mono text-[11px] uppercase tracking-wider bg-slate text-chalk px-4 py-2.5 rounded-sm"
          >
            New template
          </Link>
        )}
      </div>
      <AdminMailNav />

      {!isTech && (
        <div className="text-sm text-amber-900 mb-6 bg-amber-pale border border-amber/25 rounded-sm px-4 py-3 font-sans">
          Only <span className="font-semibold">tech admin</span> can create or archive templates.
        </div>
      )}
      {isError && <div className="text-sm text-blush mb-6">{(error as Error).message}</div>}
      {isLoading && <p className="text-sm text-slate/55">Loading…</p>}

      <div className="rounded-sm border border-border-soft bg-chalk overflow-hidden">
        {list.length === 0 && !isLoading && (
          <p className="px-5 py-8 text-sm text-slate/55">No templates yet.</p>
        )}
        {list.map((row) => (
          <div key={row.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 border-b border-border-soft last:border-0">
            <div>
              <Link to={`/admin/mail/templates/${row.id}`} className="font-sans text-sm text-slate font-medium hover:text-mint">
                {row.name}
              </Link>
              <div className="font-mono text-[10px] text-slate/50 mt-0.5">{row.subject}</div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link
                to={`/admin/mail/templates/${row.id}`}
                className="font-mono text-[10px] uppercase tracking-wider border border-border-soft px-3 py-1.5 rounded-sm"
              >
                Edit
              </Link>
              {isTech && (
                <>
                  <button
                    type="button"
                    className="font-mono text-[10px] uppercase tracking-wider border border-border-soft px-3 py-1.5 rounded-sm"
                    onClick={() => dupMut.mutate(row.id)}
                  >
                    Duplicate
                  </button>
                  <button
                    type="button"
                    className="font-mono text-[10px] uppercase tracking-wider border border-blush/30 text-blush px-3 py-1.5 rounded-sm"
                    onClick={() => archiveMut.mutate(row.id)}
                  >
                    Archive
                  </button>
                </>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
