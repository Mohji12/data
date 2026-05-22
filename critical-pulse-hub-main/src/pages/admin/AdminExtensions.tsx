import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Layers, Calendar, Clock, Banknote, CheckCircle2, XCircle } from 'lucide-react';
import { toast } from 'sonner';
import { apiClient } from '@/lib/apiClient';

interface ExtensionSetting {
  batch_id: number;
  batch_name: string;
  status: string;
  enabled: boolean;
  gross_amount: number;
  gst_percentage: number;
  gst_amount: number;
  total_amount: number;
  months: number;
  start_date: string;
  end_date: string;
}

export default function AdminExtensions() {
  const qc = useQueryClient();
  const [editing, setEditing] = useState<ExtensionSetting | null>(null);
  const [sortBy, setSortBy] = useState<string>('batch_name');
  const [order, setOrder] = useState<'asc' | 'desc'>('asc');

  const calculateAmounts = (gross: number, gstPct: number) => {
    if (!editing) return;
    const gstAmt = Math.round((gross * gstPct) / 100);
    const total = gross + gstAmt;
    setEditing({
      ...editing,
      gross_amount: gross,
      gst_percentage: gstPct,
      gst_amount: gstAmt,
      total_amount: total,
    });
  };

  const { data: settings, isLoading } = useQuery<ExtensionSetting[]>({
    queryKey: ['adminExtensionSettings'],
    queryFn: () => apiClient('/admin/commerce/extension-batch-settings'),
  });

  const updateMut = useMutation({
    mutationFn: (payload: any) => 
      apiClient('/admin/commerce/extension-batch-settings', {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['adminExtensionSettings'] });
      setEditing(null);
      toast.success('Extension settings updated');
    },
  });

  if (isLoading) {
    return <div className="p-8 text-center font-mono text-xs text-ink-muted">Loading settings…</div>;
  }

  const toggleSort = (field: string) => {
    if (sortBy === field) {
      setOrder(order === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setOrder('asc');
    }
  };

  const SortIcon = ({ field }: { field: string }) => {
    if (sortBy !== field) return <span className="opacity-20 ml-1">↕</span>;
    return <span className="ml-1 text-mint">{order === 'asc' ? '↑' : '↓'}</span>;
  };

  const sortedSettings = [...(settings || [])].sort((a: any, b: any) => {
    const valA = a[sortBy];
    const valB = b[sortBy];
    if (typeof valA === 'string') {
      return order === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
    }
    return order === 'asc' ? valA - valB : valB - valA;
  });

  return (
    <div className="p-6 lg:p-8 space-y-8">
      <header className="flex flex-col gap-1">
        <h1 className="font-display font-bold text-3xl text-slate tracking-tight">Batch Extensions</h1>
        <p className="text-ink-muted text-sm max-w-2xl">
          Configure manual extension offers for specific batches. Students will see the extension link on their dashboard only during the defined date window.
        </p>
      </header>

      <div className="bg-chalk border border-border-soft rounded-sm overflow-hidden shadow-sm">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-chalk-cool border-b border-border-soft">
              {[
                { id: 'batch_name', label: 'Batch Name' },
                { id: 'status', label: 'Status' },
                { id: 'enabled', label: 'Extension Link' },
                { id: 'months', label: 'Duration' },
                { id: 'total_amount', label: 'Price' },
                { id: 'start_date', label: 'Visibility Window' },
                { label: '' },
              ].map((h) => (
                <th
                  key={h.label}
                  onClick={() => 'id' in h && h.id && toggleSort(h.id)}
                  className={`px-4 py-3 font-mono text-[10px] text-ink-faint uppercase tracking-wider ${
                    'id' in h ? 'cursor-pointer hover:text-ink transition-colors' : ''
                  }`}
                >
                  {h.label}
                  {'id' in h && <SortIcon field={h.id!} />}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border-soft/50">
            {sortedSettings.map((s) => (
              <tr key={s.batch_id} className="hover:bg-chalk-warm/30 transition-colors">
                <td className="px-4 py-4">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-sm bg-slate/5 flex items-center justify-center text-slate">
                      <Layers size={14} />
                    </div>
                    <span className="font-sans font-medium text-sm text-slate">{s.batch_name}</span>
                  </div>
                </td>
                <td className="px-4 py-4">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium font-mono ${
                    s.status === '1' ? 'bg-mint/10 text-mint border border-mint/20' : 'bg-ink-ghost text-ink-faint border border-border-soft'
                  }`}>
                    {s.status === '1' ? 'Active Batch' : 'Inactive'}
                  </span>
                </td>
                <td className="px-4 py-4">
                  {s.enabled ? (
                    <div className="flex items-center gap-1.5 text-mint font-medium text-xs">
                      <CheckCircle2 size={14} />
                      Enabled
                    </div>
                  ) : (
                    <div className="flex items-center gap-1.5 text-ink-faint text-xs italic">
                      <XCircle size={14} />
                      Disabled
                    </div>
                  )}
                </td>
                <td className="px-4 py-4">
                  <div className="flex items-center gap-1.5 text-slate text-sm">
                    <Clock size={14} className="text-ink-faint" />
                    {s.months} Months
                  </div>
                </td>
                <td className="px-4 py-4">
                  <div className="flex flex-col">
                    <div className="flex items-center gap-1.5 font-mono text-sm text-slate font-bold">
                      <Banknote size={14} className="text-ink-faint" />
                      ₹{s.total_amount.toLocaleString()}
                    </div>
                    <span className="text-[10px] text-ink-faint italic ml-5">
                      (₹{s.gross_amount} + {s.gst_percentage}% GST)
                    </span>
                  </div>
                </td>
                <td className="px-4 py-4">
                  <div className="flex flex-col gap-0.5">
                    <div className="flex items-center gap-1.5 text-[11px] text-ink-muted">
                      <Calendar size={12} className="text-ink-faint" />
                      {s.start_date || 'No Start Date'}
                    </div>
                    <div className="flex items-center gap-1.5 text-[11px] text-ink-muted">
                      <div className="w-3" /> {/* Spacer */}
                      to {s.end_date || 'No Expiry'}
                    </div>
                  </div>
                </td>
                <td className="px-4 py-4 text-right">
                  <button
                    onClick={() => setEditing(s)}
                    className="px-3 py-1.5 bg-slate text-chalk rounded-sm text-xs font-medium hover:bg-slate/90 transition-colors"
                  >
                    Configure
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {editing && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4 backdrop-blur-sm">
          <div className="w-full max-w-lg bg-chalk border border-border-soft rounded-sm shadow-2xl overflow-hidden animate-in fade-in zoom-in duration-200">
            <div className="bg-slate px-6 py-4 flex justify-between items-center">
              <h2 className="text-chalk font-display font-bold text-lg">Configure Extension: {editing.batch_name}</h2>
              <button onClick={() => setEditing(null)} className="text-chalk/60 hover:text-chalk">
                <XCircle size={20} />
              </button>
            </div>
            
            <form className="p-6 space-y-5" onSubmit={(e) => {
              e.preventDefault();
              updateMut.mutate(editing);
            }}>
              <div className="flex items-center justify-between p-3 bg-chalk-cool rounded-sm border border-border-soft">
                <div className="flex flex-col">
                  <span className="font-sans font-bold text-sm text-slate">Display Extension Link</span>
                  <span className="text-[11px] text-ink-muted italic">Toggle the visibility of the "Extend Subscription" link on the student dashboard.</span>
                </div>
                <button
                  type="button"
                  onClick={() => setEditing({ ...editing, enabled: !editing.enabled })}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${
                    editing.enabled ? 'bg-mint' : 'bg-ink-ghost'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-chalk transition-transform ${
                      editing.enabled ? 'translate-x-6' : 'translate-x-1'
                    }`}
                  />
                </button>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="block font-mono text-[10px] text-ink-faint uppercase tracking-wider">Gross Amount (₹)</label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint text-sm">₹</span>
                    <input
                      type="number"
                      className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 pl-7 pr-3 text-sm focus:ring-1 focus:ring-slate/20 outline-none"
                      value={editing.gross_amount}
                      onChange={(e) => calculateAmounts(Number(e.target.value || 0), editing.gst_percentage)}
                    />
                  </div>
                </div>
                <div className="space-y-1.5">
                  <label className="block font-mono text-[10px] text-ink-faint uppercase tracking-wider">GST %</label>
                  <input
                    type="number"
                    className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm focus:ring-1 focus:ring-slate/20 outline-none"
                    value={editing.gst_percentage}
                    onChange={(e) => calculateAmounts(editing.gross_amount, Number(e.target.value || 0))}
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="block font-mono text-[10px] text-ink-faint uppercase tracking-wider">GST Amount (₹)</label>
                  <input
                    readOnly
                    className="w-full bg-ink-ghost border border-border-soft rounded-sm py-2 px-3 text-sm outline-none cursor-not-allowed"
                    value={editing.gst_amount}
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="block font-mono text-[10px] text-ink-faint uppercase tracking-wider">Final Payable (Total)</label>
                  <input
                    readOnly
                    className="w-full bg-ink-ghost border border-border-soft rounded-sm py-2 px-3 text-sm font-bold text-slate outline-none cursor-not-allowed"
                    value={editing.total_amount}
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="block font-mono text-[10px] text-ink-faint uppercase tracking-wider">Extension Months</label>
                <select
                  className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm focus:ring-1 focus:ring-slate/20 outline-none"
                  value={editing.months}
                  onChange={(e) => setEditing({ ...editing, months: Number(e.target.value) })}
                >
                  {[1, 2, 3, 4, 5, 6].map(m => (
                    <option key={m} value={m}>{m} {m === 1 ? 'Month' : 'Months'}</option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5 pt-2">
                <label className="block font-mono text-[10px] text-ink-faint uppercase tracking-wider">Visibility Window (Start & End Date)</label>
                <div className="grid grid-cols-2 gap-4">
                  <div className="relative">
                    <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" size={14} />
                    <input
                      type="date"
                      className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 pl-9 pr-3 text-sm focus:ring-1 focus:ring-slate/20 outline-none"
                      value={editing.start_date}
                      onChange={(e) => setEditing({ ...editing, start_date: e.target.value })}
                    />
                  </div>
                  <div className="relative">
                    <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" size={14} />
                    <input
                      type="date"
                      className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 pl-9 pr-3 text-sm focus:ring-1 focus:ring-slate/20 outline-none"
                      value={editing.end_date}
                      onChange={(e) => setEditing({ ...editing, end_date: e.target.value })}
                    />
                  </div>
                </div>
                <p className="text-[10px] text-ink-muted italic">Leaving dates blank means the link will be shown permanently while "Display" is on.</p>
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t border-border-soft">
                <button
                  type="button"
                  onClick={() => setEditing(null)}
                  className="px-5 py-2 text-xs font-medium text-ink-muted hover:text-slate transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={updateMut.isPending}
                  className="px-6 py-2 bg-slate text-chalk rounded-sm text-xs font-bold disabled:opacity-50 hover:bg-slate/90 transition-all flex items-center gap-2"
                >
                  {updateMut.isPending ? 'Saving Settings…' : 'Save Configuration'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
