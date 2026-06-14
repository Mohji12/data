// WhatsApp Communication Admin Page
import { useState, useMemo } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/apiClient';
import { toast } from 'sonner';
import { Search, MessageCircle, Copy, Users, CheckCircle2, XCircle, Clock } from 'lucide-react';

type BatchRow = { id: number; name: string; status: string };

type AdminUserRow = {
  id: number;
  subscription?: string | null;
  name?: string | null;
  email?: string | null;
  contact_number?: string | null;
  approve?: string | null;
  payment_status?: string | null;
};

export default function AdminWhatsApp() {
  const [q, setQ] = useState('');
  const [subscriptions, setSubscriptions] = useState<string[]>([]);
  const [approve, setApprove] = useState('');
  const [message, setMessage] = useState('');
  const [sendMode, setSendMode] = useState<'text' | 'template'>('template');
  const [templateName, setTemplateName] = useState('');
  const [templateLanguage, setTemplateLanguage] = useState('en');
  const [templateBodyParams, setTemplateBodyParams] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [externalNumbers, setExternalNumbers] = useState('');
  
  // Bulk sending state
  const [selectedUserIds, setSelectedUserIds] = useState<Set<number>>(new Set());
  const [bulkStep, setBulkStep] = useState<number | null>(null); // null means modal closed, index otherwise
  const [isBatchDropdownOpen, setIsBatchDropdownOpen] = useState(false);
  const [apiResult, setApiResult] = useState<{
    total: number;
    sent: number;
    failed: number;
    failures: { phone: string; error?: string; status_code?: number }[];
  } | null>(null);
  const queryClient = useQueryClient();

  // Fetch template from backend
  useQuery({
    queryKey: ['whatsappTemplate'],
    queryFn: async () => {
      const res = await apiClient('/admin/whatsapp/template');
      setMessage(res.template);
      if (res.default_template_name) setTemplateName(res.default_template_name);
      if (res.default_template_language) setTemplateLanguage(res.default_template_language);
      return res;
    },
    staleTime: Infinity,
  });

  const saveTemplate = async () => {
    try {
      setIsSaving(true);
      await apiClient('/admin/whatsapp/template', {
        method: 'POST',
        body: JSON.stringify({ template: message }),
      });
      toast.success('Template saved successfully');
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setIsSaving(false);
    }
  };

  const logWhatsAppAction = async (userId: number) => {
    try {
      await apiClient('/admin/whatsapp/log', {
        method: 'POST',
        body: JSON.stringify({ user_id: userId, message }),
      });
    } catch (e) {
      console.error('Failed to log WhatsApp action', e);
    }
  };

  const queryString = useMemo(() => {
    const p = new URLSearchParams();
    if (q.trim()) p.set('q', q.trim());
    if (subscriptions.length > 0) {
      subscriptions.forEach(s => p.append('subscription', s));
    }
    if (approve !== '') p.set('approve', approve);
    p.set('limit', '500'); // Load more for communication
    return p.toString();
  }, [q, subscriptions, approve]);

  const { data: batches } = useQuery({
    queryKey: ['adminMiscBatches'],
    queryFn: () => apiClient('/admin/misc/batches') as Promise<BatchRow[]>,
  });

  const { data, isLoading } = useQuery({
    queryKey: ['adminUsers', queryString],
    queryFn: () => apiClient(`/admin/users?${queryString}`),
  });

  const users = (data?.items || []) as AdminUserRow[];
  const activeBatches = (batches || []).filter((b) => String(b.status ?? '1') === '1');

  const copyNumbers = () => {
    const numbers = users
      .map((u) => u.contact_number?.trim())
      .filter(Boolean)
      .join(', ');
    if (!numbers) {
      toast.error('No contact numbers found in current filter');
      return;
    }
    navigator.clipboard.writeText(numbers);
    toast.success('All contact numbers copied to clipboard');
  };

  const openWhatsApp = (phone: string, userId?: number) => {
    let cleanPhone = phone.replace(/\D/g, '');
    if (!cleanPhone) {
      toast.error('Invalid phone number');
      return;
    }
    // If it's 10 digits, assume India (+91)
    if (cleanPhone.length === 10) {
      cleanPhone = '91' + cleanPhone;
    }
    const encodedMsg = encodeURIComponent(message);
    
    if (userId) logWhatsAppAction(userId);
    
    window.open(`https://wa.me/${cleanPhone}?text=${encodedMsg}`, '_blank');
  };

  const selectedUsers = users.filter(u => selectedUserIds.has(u.id));

  const toggleUserSelection = (userId: number) => {
    const next = new Set(selectedUserIds);
    if (next.has(userId)) next.delete(userId);
    else next.add(userId);
    setSelectedUserIds(next);
  };

  const toggleAllUsers = () => {
    if (selectedUserIds.size === users.length && users.length > 0) {
      setSelectedUserIds(new Set());
    } else {
      setSelectedUserIds(new Set(users.map(u => u.id)));
    }
  };

  const toggleSubscription = (name: string) => {
    setSubscriptions(prev => 
      prev.includes(name) ? prev.filter(s => s !== name) : [...prev, name]
    );
  };

  const parsedExternalNumbers = useMemo(() => {
    return externalNumbers
      .split(/[\n,]/)
      .map(n => n.trim().replace(/\D/g, ''))
      .filter(n => n.length >= 10);
  }, [externalNumbers]);

  const allRecipients = useMemo(() => {
    const fromUsers = selectedUsers.map(u => ({
      id: u.id,
      name: u.name || 'User',
      phone: u.contact_number || '',
      isExternal: false
    }));
    const fromExternal = parsedExternalNumbers.map((n, i) => ({
      id: -1000 - i,
      name: `External ${i + 1}`,
      phone: n,
      isExternal: true
    }));
    return [...fromUsers, ...fromExternal];
  }, [selectedUsers, parsedExternalNumbers]);

  const bulkSendMutation = useMutation({
    mutationFn: async () => {
      if (allRecipients.length === 0) {
        throw new Error('Please select users or add external numbers');
      }
      if (sendMode === 'text' && !message.trim()) {
        throw new Error('Message is required for text mode');
      }
      if (sendMode === 'template' && !templateName.trim()) {
        throw new Error('Template name is required for template mode');
      }
      const recipients = allRecipients.map((r) => ({
        user_id: r.isExternal ? null : r.id,
        name: r.name,
        phone: r.phone,
      }));
      const bodyParams = templateBodyParams
        .split(/[\n,]/)
        .map((p) => p.trim())
        .filter(Boolean);
      return apiClient('/admin/whatsapp/bulk-send', {
        method: 'POST',
        body: JSON.stringify({
          send_mode: sendMode,
          message: sendMode === 'text' ? message.trim() : null,
          template_name: sendMode === 'template' ? templateName.trim() : null,
          template_language: templateLanguage.trim() || 'en',
          template_body_params: sendMode === 'template' ? bodyParams : [],
          recipients,
          dedupe: true,
        }),
      });
    },
    onSuccess: (res: any) => {
      setApiResult({
        total: Number(res?.total || 0),
        sent: Number(res?.sent || 0),
        failed: Number(res?.failed || 0),
        failures: Array.isArray(res?.failures) ? res.failures : [],
      });
      toast.success(`Bulk dispatch finished. Sent ${res?.sent || 0}/${res?.total || 0}`);
      queryClient.invalidateQueries({ queryKey: ['adminUsers'] });
    },
    onError: (e: any) => {
      toast.error(e?.message || 'Bulk dispatch failed');
    },
  });

  const startBulkSend = () => {
    if (allRecipients.length === 0) {
      toast.error('Please select users or add external numbers');
      return;
    }
    setBulkStep(0);
  };

  const nextBulkStep = () => {
    if (bulkStep === null) return;
    if (bulkStep < allRecipients.length - 1) {
      setBulkStep(bulkStep + 1);
    } else {
      setBulkStep(null);
      toast.success('Bulk sending sequence completed');
    }
  };

  return (
    <div className="p-6 lg:p-8 space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="font-display font-bold text-3xl text-slate">WhatsApp Communication</h1>
          <p className="font-mono text-[11px] text-ink-faint mt-1 uppercase tracking-wider">
            Directly message users or copy numbers for group management
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 space-y-6">
          <div className="bg-chalk border border-border-soft rounded-sm p-6 space-y-4 shadow-sm">
            <h3 className="font-sans text-sm font-semibold text-slate flex items-center gap-2">
              <MessageCircle size={16} className="text-mint" />
              Message Template
            </h3>
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Type your message here..."
              rows={6}
              className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm focus:outline-none focus:border-mint transition-colors"
            />
            <button
              onClick={saveTemplate}
              disabled={isSaving || !message.trim()}
              className="w-full bg-mint text-slate rounded-sm px-4 py-2 font-sans text-[11px] font-bold hover:bg-mint-light transition-all disabled:opacity-50"
            >
              {isSaving ? 'Saving...' : 'Save as Default Template'}
            </button>
            <p className="text-[10px] text-ink-faint">
              This message will be pre-filled when you click the WhatsApp icon next to a user.
            </p>
          </div>

          <div className="bg-chalk border border-border-soft rounded-sm p-6 space-y-4 shadow-sm">
            <h3 className="font-sans text-sm font-semibold text-slate flex items-center gap-2">
              <Users size={16} className="text-sky-500" />
              External Numbers
            </h3>
            <textarea
              value={externalNumbers}
              onChange={(e) => setExternalNumbers(e.target.value)}
              placeholder="Paste numbers here (comma or newline separated)..."
              rows={4}
              className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm focus:outline-none focus:border-mint transition-colors"
            />
            <div className="flex flex-col gap-2">
              <button
                onClick={copyNumbers}
                className="w-full inline-flex items-center justify-center gap-2 bg-slate text-chalk rounded-sm px-4 py-2 font-sans text-[11px] font-semibold hover:bg-slate-light transition-all"
              >
                <Copy size={12} />
                Copy Filtered Numbers
              </button>
              <button
                onClick={startBulkSend}
                disabled={allRecipients.length === 0}
                className="w-full bg-mint text-slate px-4 py-2 rounded-sm font-sans text-[11px] font-bold hover:bg-mint-light transition-all shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {allRecipients.length > 0 ? `Start Manual Bulk Sequence (${allRecipients.length})` : 'Start Manual Bulk Sequence'}
              </button>
            </div>
          </div>

          <div className="bg-chalk border border-border-soft rounded-sm p-6 space-y-4 shadow-sm">
            <h3 className="font-sans text-sm font-semibold text-slate flex items-center gap-2">
              <MessageCircle size={16} className="text-blush" />
              API Bulk Dispatch
            </h3>
            <div className="space-y-2">
              <label className="font-mono text-[10px] text-ink-faint uppercase tracking-wide">Send mode</label>
              <select
                value={sendMode}
                onChange={(e) => setSendMode(e.target.value as 'text' | 'template')}
                className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm focus:outline-none focus:border-mint transition-colors"
              >
                <option value="template">Approved template (recommended for bulk)</option>
                <option value="text">Free text (24h reply window only)</option>
              </select>
            </div>
            {sendMode === 'template' ? (
              <div className="space-y-3">
                <div>
                  <label className="font-mono text-[10px] text-ink-faint uppercase tracking-wide">Template name</label>
                  <input
                    value={templateName}
                    onChange={(e) => setTemplateName(e.target.value)}
                    placeholder="e.g. hello_world"
                    className="mt-1 w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm focus:outline-none focus:border-mint transition-colors"
                  />
                </div>
                <div>
                  <label className="font-mono text-[10px] text-ink-faint uppercase tracking-wide">Language code</label>
                  <input
                    value={templateLanguage}
                    onChange={(e) => setTemplateLanguage(e.target.value)}
                    placeholder="en or en_US"
                    className="mt-1 w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm focus:outline-none focus:border-mint transition-colors"
                  />
                </div>
                <div>
                  <label className="font-mono text-[10px] text-ink-faint uppercase tracking-wide">Body variables (optional)</label>
                  <textarea
                    value={templateBodyParams}
                    onChange={(e) => setTemplateBodyParams(e.target.value)}
                    placeholder="One per line or comma-separated for {{1}}, {{2}}, ..."
                    rows={3}
                    className="mt-1 w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm focus:outline-none focus:border-mint transition-colors"
                  />
                </div>
              </div>
            ) : (
              <p className="text-[10px] text-ink-faint">
                Free text only works if each recipient messaged your business number within the last 24 hours.
              </p>
            )}
            <button
              disabled={
                bulkSendMutation.isPending ||
                allRecipients.length === 0 ||
                (sendMode === 'text' ? !message.trim() : !templateName.trim())
              }
              onClick={() => bulkSendMutation.mutate()}
              className="w-full bg-slate text-chalk rounded-sm px-4 py-2 font-sans text-[11px] font-bold hover:bg-slate-light transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {bulkSendMutation.isPending ? 'Sending via API...' : `Send via API (${allRecipients.length})`}
            </button>
            {apiResult && (
              <div className="rounded-sm border border-border-soft bg-chalk-warm p-3 space-y-1">
                <p className="font-mono text-[10px] text-slate uppercase tracking-wide">
                  Result: {apiResult.sent}/{apiResult.total} sent, {apiResult.failed} failed
                </p>
                {apiResult.failures.length > 0 && (
                  <div className="max-h-24 overflow-y-auto space-y-1">
                    {apiResult.failures.slice(0, 5).map((f, idx) => (
                      <p key={`${f.phone}-${idx}`} className="text-[10px] text-ink-faint break-all">
                        {f.phone}: {f.error || `HTTP ${f.status_code || 'error'}`}
                      </p>
                    ))}
                  </div>
                )}
              </div>
            )}
            <p className="text-[10px] text-ink-faint">
              API key is kept only on backend. Use an approved Meta template for cold bulk outreach.
            </p>
          </div>
        </div>

        <div className="lg:col-span-2 space-y-6">
          <div className="bg-chalk border border-border-soft rounded-sm p-6 shadow-sm">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" size={14} />
                <input
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  placeholder="Search name/email/phone..."
                  className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 pl-9 pr-3 text-sm focus:outline-none focus:border-mint transition-colors"
                />
              </div>
              
              <div className="relative">
                <button
                  onClick={() => setIsBatchDropdownOpen(!isBatchDropdownOpen)}
                  className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm text-left flex items-center justify-between hover:border-mint transition-colors"
                >
                  <span className="truncate">
                    {subscriptions.length === 0 ? 'All Batches' : `${subscriptions.length} Batches Selected`}
                  </span>
                  <Users size={14} className="text-ink-faint" />
                </button>
                {isBatchDropdownOpen && (
                  <>
                    <div className="fixed inset-0 z-10" onClick={() => setIsBatchDropdownOpen(false)} />
                    <div className="absolute top-full left-0 right-0 mt-1 bg-chalk border border-border-soft rounded-sm shadow-xl z-20 max-h-60 overflow-y-auto p-2 space-y-1">
                      {activeBatches.map((b) => (
                        <label key={b.id} className="flex items-center gap-2 px-2 py-1.5 hover:bg-chalk-warm rounded-sm cursor-pointer transition-colors">
                          <input
                            type="checkbox"
                            checked={subscriptions.includes(b.name)}
                            onChange={() => toggleSubscription(b.name)}
                            className="rounded-sm border-border-soft text-mint focus:ring-mint"
                          />
                          <span className="text-xs text-slate font-medium">{b.name}</span>
                        </label>
                      ))}
                      {activeBatches.length === 0 && (
                        <div className="p-2 text-center text-ink-faint text-[10px]">No active batches</div>
                      )}
                    </div>
                  </>
                )}
              </div>

              <select
                value={approve}
                onChange={(e) => setApprove(e.target.value)}
                className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm focus:outline-none focus:border-mint transition-colors"
              >
                <option value="">Approval Status</option>
                <option value="1">Approved</option>
                <option value="0">Pending</option>
              </select>
            </div>
          </div>

          <div className="bg-chalk border border-border-soft rounded-sm overflow-hidden shadow-sm flex flex-col">
            <div className="overflow-x-auto overflow-y-auto max-h-[600px]">
              <table className="w-full text-left border-collapse">
                <thead className="sticky top-0 z-10">
                  <tr className="bg-chalk-cool border-b border-border-soft">
                    <th className="px-4 py-3 w-10 bg-chalk-cool">
                      <input
                        type="checkbox"
                        checked={users.length > 0 && selectedUserIds.size === users.length}
                        onChange={toggleAllUsers}
                        className="rounded-sm border-border-soft text-mint focus:ring-mint"
                      />
                    </th>
                    <th className="px-4 py-3 font-mono text-[10px] text-slate-dark uppercase tracking-wider bg-chalk-cool">User</th>
                    <th className="px-4 py-3 font-mono text-[10px] text-slate-dark uppercase tracking-wider bg-chalk-cool">Batch</th>
                    <th className="px-4 py-3 font-mono text-[10px] text-slate-dark uppercase tracking-wider text-center bg-chalk-cool">WhatsApp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-soft">
                  {isLoading ? (
                    <tr>
                      <td colSpan={4} className="px-4 py-12 text-center text-ink-faint animate-pulse font-mono text-xs">
                        Fetching users...
                      </td>
                    </tr>
                  ) : users.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="px-4 py-12 text-center text-ink-muted font-sans text-sm">
                        No users found matching your criteria.
                      </td>
                    </tr>
                  ) : (
                    users.map((u) => (
                      <tr key={u.id} className={`hover:bg-chalk-warm transition-colors ${selectedUserIds.has(u.id) ? 'bg-mint/5' : ''}`}>
                        <td className="px-4 py-4">
                          <input
                            type="checkbox"
                            checked={selectedUserIds.has(u.id)}
                            onChange={() => toggleUserSelection(u.id)}
                            className="rounded-sm border-border-soft text-mint focus:ring-mint"
                          />
                        </td>
                        <td className="px-4 py-4" onClick={() => toggleUserSelection(u.id)}>
                          <div className="flex items-center gap-3 cursor-pointer">
                            <div className="w-8 h-8 rounded-full bg-slate/5 border border-border-soft flex items-center justify-center text-slate font-display font-bold text-xs shrink-0">
                              {u.name?.charAt(0) || '?'}
                            </div>
                            <div className="min-w-0">
                              <div className="font-sans text-sm font-semibold text-slate truncate">
                                {u.name || 'Unknown'}
                                {u.approve === '1' ? (
                                  <CheckCircle2 size={12} className="inline ml-1.5 text-mint" />
                                ) : u.approve === '0' ? (
                                  <Clock size={12} className="inline ml-1.5 text-amber" />
                                ) : (
                                  <XCircle size={12} className="inline ml-1.5 text-blush" />
                                )}
                              </div>
                              <div className="font-mono text-[10px] text-ink-faint truncate">{u.contact_number || 'No phone'}</div>
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-4 font-mono text-[10px] text-slate-light">
                          <span className="bg-sky-50 border border-sky-100 rounded-sm px-2 py-0.5 whitespace-nowrap">
                            {u.subscription || 'N/A'}
                          </span>
                        </td>
                        <td className="px-4 py-4 text-center">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              openWhatsApp(u.contact_number || '', u.id);
                            }}
                            disabled={!u.contact_number}
                            className="p-2 rounded-sm text-mint border border-mint/20 hover:bg-mint/10 transition-colors disabled:opacity-30 disabled:hover:bg-transparent"
                            title="Message on WhatsApp"
                          >
                            <MessageCircle size={18} />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            {!isLoading && users.length > 0 && (
              <div className="bg-chalk-cool p-3 flex items-center justify-between border-t border-border-soft sticky bottom-0 z-10 shadow-[0_-2px_10px_rgba(0,0,0,0.05)]">
                <span className="font-mono text-[10px] text-ink-faint uppercase">
                  Showing {users.length} matching users
                </span>
                <div className="flex items-center gap-4">
                  <span className="font-sans text-xs font-semibold text-mint">
                    {allRecipients.length > 0 ? `${allRecipients.length} recipients selected` : 'No recipients selected'}
                  </span>
                  <button
                    onClick={startBulkSend}
                    disabled={allRecipients.length === 0}
                    className="bg-mint text-slate px-4 py-1.5 rounded-sm font-sans text-[11px] font-bold hover:bg-mint-light transition-all shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Send Bulk WhatsApp
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Bulk Send Sequence Modal */}
      {bulkStep !== null && allRecipients[bulkStep] && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate/60 backdrop-blur-sm">
          <div className="w-full max-w-md bg-chalk rounded-sm shadow-2xl border border-border-soft p-8 space-y-6 animate-in fade-in zoom-in duration-200">
            <div className="text-center space-y-2">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-mint/10 text-mint mb-2">
                <MessageCircle size={32} />
              </div>
              <h2 className="font-display font-bold text-2xl text-slate">Bulk Sending</h2>
              <p className="font-mono text-[10px] text-ink-faint uppercase tracking-widest">
                Message {bulkStep + 1} of {allRecipients.length}
              </p>
            </div>

            <div className="bg-chalk-warm rounded-sm p-4 border border-border-soft">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-full bg-slate text-chalk flex items-center justify-center font-display font-bold text-lg">
                  {allRecipients[bulkStep].name?.charAt(0) || '?'}
                </div>
                <div className="min-w-0">
                  <div className="font-sans text-sm font-bold text-slate truncate">{allRecipients[bulkStep].name}</div>
                  <div className="font-mono text-[11px] text-ink-faint">{allRecipients[bulkStep].phone}</div>
                </div>
                {allRecipients[bulkStep].isExternal && (
                  <span className="ml-auto text-[8px] bg-slate/10 text-slate px-1.5 py-0.5 rounded-full font-mono uppercase font-bold">External</span>
                )}
              </div>
            </div>

            <div className="space-y-3 pt-2">
              <button
                onClick={() => {
                  openWhatsApp(allRecipients[bulkStep].phone || '', !allRecipients[bulkStep].isExternal ? allRecipients[bulkStep].id : undefined);
                  nextBulkStep();
                }}
                className="w-full bg-mint text-slate py-3 rounded-sm font-sans font-bold hover:bg-mint-light transition-all flex items-center justify-center gap-2 shadow-sm"
              >
                Send Message & Next
                <CheckCircle2 size={16} />
              </button>
              <div className="flex gap-3">
                <button
                  onClick={nextBulkStep}
                  className="flex-1 bg-chalk-cool text-slate py-2 rounded-sm font-sans text-xs font-semibold hover:bg-chalk-warm transition-all border border-border-soft"
                >
                  Skip This User
                </button>
                <button
                  onClick={() => setBulkStep(null)}
                  className="flex-1 bg-chalk-cool text-slate py-2 rounded-sm font-sans text-xs font-semibold hover:bg-chalk-warm transition-all border border-border-soft"
                >
                  Cancel Sequence
                </button>
              </div>
            </div>

            <div className="w-full bg-chalk-warm rounded-full h-1.5 overflow-hidden">
              <div 
                className="bg-mint h-full transition-all duration-300" 
                style={{ width: `${((bulkStep + 1) / allRecipients.length) * 100}%` }}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
