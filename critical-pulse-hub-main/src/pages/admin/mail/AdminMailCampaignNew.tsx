import { useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { apiClient } from '@/lib/apiClient';
import { useIsTechAdmin } from '@/store/authStore';
import AdminMailNav from './AdminMailNav';
import { toIstDatetimeLocal, type AudiencePreview, type MailCampaign, type MailTemplate } from './mailTypes';

type BatchRow = { id: number; name: string };

export default function AdminMailCampaignNew() {
  const isTech = useIsTechAdmin();
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [name, setName] = useState('');
  const [templateId, setTemplateId] = useState<number | ''>('');
  const [subjectOverride, setSubjectOverride] = useState('');
  const [audienceType, setAudienceType] = useState<'batch' | 'all' | 'list'>('list');
  const [batches, setBatches] = useState<string[]>([]);
  const [pasted, setPasted] = useState('');
  const [sendMode, setSendMode] = useState<'now' | 'later'>('now');
  const [scheduledAt, setScheduledAt] = useState(toIstDatetimeLocal());
  const [batchSize, setBatchSize] = useState(100);
  const [pauseMinutes, setPauseMinutes] = useState(5);
  const [preview, setPreview] = useState<AudiencePreview | null>(null);
  const [createdId, setCreatedId] = useState<number | null>(null);
  const [skipBounced, setSkipBounced] = useState(true);
  const [excludeEmails, setExcludeEmails] = useState<string[]>([]);

  const templates = useQuery({
    queryKey: ['adminMailTemplates'],
    queryFn: () => apiClient('/admin/mail/templates') as Promise<MailTemplate[]>,
  });
  const batchRows = useQuery({
    queryKey: ['adminMailBatches'],
    queryFn: () => apiClient('/admin/mail/batches') as Promise<BatchRow[]>,
  });

  const audience = useMemo(() => {
    if (audienceType === 'batch') return { batches };
    if (audienceType === 'list') return { pasted };
    return {};
  }, [audienceType, batches, pasted]);

  const previewMut = useMutation({
    mutationFn: () =>
      apiClient('/admin/mail/audience/preview', {
        method: 'POST',
        body: JSON.stringify({
          audience_type: audienceType,
          audience,
          skip_previously_bounced: skipBounced,
          exclude_emails: excludeEmails,
          check_dns: true,
        }),
      }) as Promise<AudiencePreview>,
    onSuccess: (res) => setPreview(res),
    onError: (e: Error) => toast.error(e.message),
  });

  const createMut = useMutation({
    mutationFn: () =>
      apiClient('/admin/mail/campaigns', {
        method: 'POST',
        body: JSON.stringify({
          name,
          template_id: templateId,
          subject_override: subjectOverride || null,
          audience_type: audienceType,
          audience,
          send_mode: sendMode,
          scheduled_at_ist: sendMode === 'later' ? scheduledAt : null,
          send_batch_size: batchSize,
          send_pause_minutes: pauseMinutes,
          skip_previously_bounced: skipBounced,
          exclude_emails: excludeEmails,
        }),
      }) as Promise<MailCampaign>,
    onSuccess: (row) => {
      setCreatedId(row.id);
      setStep(4);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const confirmMut = useMutation({
    mutationFn: (id: number) =>
      apiClient(`/admin/mail/campaigns/${id}/confirm`, {
        method: 'POST',
        body: JSON.stringify({ confirm: true }),
      }) as Promise<MailCampaign>,
    onSuccess: (row) => {
      toast.success(row.status === 'scheduled' ? 'Scheduled' : 'Sending');
      navigate(`/admin/mail/campaigns/${row.id}`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const field = 'w-full bg-chalk-warm border border-border-soft rounded-sm py-2.5 px-3 font-sans text-sm text-slate focus:outline-none focus:ring-2 focus:ring-mint/25';

  if (!isTech) {
    return (
      <div className="p-6 lg:p-8">
        <AdminMailNav />
        <div className="text-sm text-amber-900 bg-amber-pale border border-amber/25 rounded-sm px-4 py-3">
          Only tech admin can create and send campaigns.
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8 min-w-0 max-w-full">
      <div className="flex items-start justify-between gap-6 mb-6">
        <div>
          <h1 className="font-display font-bold text-3xl text-slate">New campaign</h1>
          <p className="font-mono text-[11px] text-slate/55 mt-1.5 uppercase tracking-[0.14em]">
            Template · paste list or batches · waves · IST · confirm
          </p>
        </div>
        <Link to="/admin/mail/campaigns" className="font-mono text-[11px] uppercase tracking-wider border border-border-soft px-4 py-2.5 rounded-sm">
          Cancel
        </Link>
      </div>
      <AdminMailNav />

      <div className="font-mono text-[10px] uppercase tracking-wider text-slate/50 mb-4">Step {step} of 4</div>

      {step === 1 && (
        <section className="rounded-sm border border-border-soft bg-chalk p-5 space-y-4 max-w-xl">
          <label className="block">
            <span className="font-mono text-[10px] text-slate/65 uppercase tracking-wider block mb-2">Campaign name</span>
            <input className={field} value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="block">
            <span className="font-mono text-[10px] text-slate/65 uppercase tracking-wider block mb-2">Template</span>
            <select className={field} value={templateId} onChange={(e) => setTemplateId(e.target.value ? Number(e.target.value) : '')}>
              <option value="">Select…</option>
              {(templates.data ?? []).map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="font-mono text-[10px] text-slate/65 uppercase tracking-wider block mb-2">Subject override (optional)</span>
            <input className={field} value={subjectOverride} onChange={(e) => setSubjectOverride(e.target.value)} />
          </label>
          <button
            type="button"
            className="font-mono text-[11px] uppercase tracking-wider bg-slate text-chalk px-4 py-2.5 rounded-sm disabled:opacity-40"
            disabled={!name.trim() || !templateId}
            onClick={() => setStep(2)}
          >
            Next
          </button>
        </section>
      )}

      {step === 2 && (
        <section className="rounded-sm border border-border-soft bg-chalk p-5 space-y-4 max-w-2xl">
          <div className="flex flex-wrap gap-2">
            {(['list', 'batch', 'all'] as const).map((k) => (
              <button
                key={k}
                type="button"
                className={`font-mono text-[10px] uppercase px-3 py-1.5 rounded-sm border ${
                  audienceType === k ? 'bg-slate text-chalk border-slate' : 'border-border-soft'
                }`}
                onClick={() => {
                  setAudienceType(k);
                  setPreview(null);
                }}
              >
                {k === 'all' ? 'All eligible' : k === 'list' ? 'Paste emails' : 'Batches'}
              </button>
            ))}
          </div>
          {audienceType === 'batch' && (
            <div className="flex flex-wrap gap-2">
              {(batchRows.data ?? []).map((b) => {
                const on = batches.includes(b.name);
                return (
                  <button
                    key={b.id}
                    type="button"
                    className={`font-mono text-[10px] px-3 py-1.5 rounded-sm border ${
                      on ? 'bg-mint-pale border-mint/30 text-mint' : 'border-border-soft'
                    }`}
                    onClick={() =>
                      setBatches((cur) => (on ? cur.filter((n) => n !== b.name) : [...cur, b.name]))
                    }
                  >
                    {b.name}
                  </button>
                );
              })}
            </div>
          )}
          {audienceType === 'list' && (
            <label className="block">
              <span className="font-mono text-[10px] text-slate/65 uppercase tracking-wider block mb-2">
                Paste every email to send
              </span>
              <textarea
                className={`${field} min-h-[180px] font-mono text-xs`}
                placeholder={'one@example.com\ntwo@example.com\nthree@example.com'}
                value={pasted}
                onChange={(e) => setPasted(e.target.value)}
              />
              <p className="mt-2 text-xs text-slate/55">
                One per line, or comma / semicolon separated. Optional CSV: email,name,batch.
              </p>
            </label>
          )}
          <label className="flex items-center gap-2 text-sm text-slate">
            <input type="checkbox" checked={skipBounced} onChange={(e) => { setSkipBounced(e.target.checked); setPreview(null); }} />
            Skip previously bounced
          </label>
          <p className="text-xs text-slate/55">Unsubscribed and complaint addresses are always skipped. Unverified is not the same as invalid.</p>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="font-mono text-[11px] uppercase border border-border-soft px-4 py-2.5 rounded-sm" onClick={() => setStep(1)}>
              Back
            </button>
            <button
              type="button"
              className="font-mono text-[11px] uppercase bg-slate text-chalk px-4 py-2.5 rounded-sm"
              onClick={() => previewMut.mutate()}
            >
              Preview audience
            </button>
            <button
              type="button"
              className="font-mono text-[11px] uppercase border border-mint/30 bg-mint-pale text-mint px-4 py-2.5 rounded-sm disabled:opacity-40"
              disabled={!preview || preview.count < 1}
              onClick={() => setStep(3)}
            >
              Next
            </button>
          </div>
          {preview && (
            <div className="text-sm font-sans text-slate space-y-2">
              <p>
                <strong>{preview.count}</strong> eligible
                {preview.duplicate_count ? ` · ${preview.duplicate_count} duplicates` : ''}
                {preview.invalid_count ? ` · ${preview.invalid_count} invalid` : ''}
                {preview.unverified_count ? ` · ${preview.unverified_count} unverified (DNS)` : ''}
                {preview.previously_bounced_count ? ` · ${preview.previously_bounced_count} bounced` : ''}
                {preview.disposable_count ? ` · ${preview.disposable_count} disposable` : ''}
                {preview.unsubscribed_count ? ` · ${preview.unsubscribed_count} unsubscribed` : ''}
                {preview.complaints_count ? ` · ${preview.complaints_count} complaints` : ''}
                {preview.role_warning_count ? ` · ${preview.role_warning_count} role warnings` : ''}
              </p>
              <ul className="mt-2 font-mono text-[11px] text-slate/60 space-y-1">
                {preview.preview.map((r) => (
                  <li key={`${r.email}-${r.flag || 'ok'}`} className="flex flex-wrap items-center gap-2">
                    <span>
                      {r.email} {r.name ? `· ${r.name}` : ''} {r.flag ? `· ${r.flag}` : ''}
                    </span>
                    {r.flag && r.flag !== 'invalid' && r.flag !== 'unsubscribed' && r.flag !== 'complaint' && r.flag !== 'disposable' && r.flag !== 'previously_bounced' && (
                      <button
                        type="button"
                        className="uppercase text-[10px] text-blush"
                        onClick={() => {
                          setExcludeEmails((cur) => (cur.includes(r.email) ? cur : [...cur, r.email]));
                          setPreview(null);
                        }}
                      >
                        Exclude
                      </button>
                    )}
                  </li>
                ))}
              </ul>
              {excludeEmails.length > 0 && (
                <p className="text-xs text-slate/55">Excluded: {excludeEmails.join(', ')}</p>
              )}
            </div>
          )}
        </section>
      )}

      {step === 3 && (
        <section className="rounded-sm border border-border-soft bg-chalk p-5 space-y-4 max-w-xl">
          <div className="flex gap-2">
            {(['now', 'later'] as const).map((m) => (
              <button
                key={m}
                type="button"
                className={`font-mono text-[10px] uppercase px-3 py-1.5 rounded-sm border ${
                  sendMode === m ? 'bg-slate text-chalk border-slate' : 'border-border-soft'
                }`}
                onClick={() => setSendMode(m)}
              >
                {m === 'now' ? 'Send now' : 'Schedule IST'}
              </button>
            ))}
          </div>
          {sendMode === 'later' && (
            <label className="block">
              <span className="font-mono text-[10px] text-slate/65 uppercase tracking-wider block mb-2">Schedule (Asia/Kolkata)</span>
              <input type="datetime-local" className={field} value={scheduledAt} onChange={(e) => setScheduledAt(e.target.value)} />
            </label>
          )}
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="font-mono text-[10px] text-slate/65 uppercase tracking-wider block mb-2">Emails per wave</span>
              <input
                type="number"
                min={1}
                max={5000}
                className={field}
                value={batchSize}
                onChange={(e) => setBatchSize(Math.max(1, Math.min(5000, Number(e.target.value) || 1)))}
              />
            </label>
            <label className="block">
              <span className="font-mono text-[10px] text-slate/65 uppercase tracking-wider block mb-2">Wait between waves (min)</span>
              <input
                type="number"
                min={0}
                max={1440}
                className={field}
                value={pauseMinutes}
                onChange={(e) => setPauseMinutes(Math.max(0, Math.min(1440, Number(e.target.value) || 0)))}
              />
            </label>
          </div>
          <p className="text-sm text-slate/70">
            {preview?.count ?? 0} recipients · send {batchSize} emails
            {pauseMinutes > 0 ? `, then wait ${pauseMinutes} min, repeat` : ' without pausing'} · template #{templateId}
          </p>
          <div className="flex gap-2">
            <button type="button" className="font-mono text-[11px] uppercase border border-border-soft px-4 py-2.5 rounded-sm" onClick={() => setStep(2)}>
              Back
            </button>
            <button
              type="button"
              className="font-mono text-[11px] uppercase bg-slate text-chalk px-4 py-2.5 rounded-sm"
              disabled={createMut.isPending}
              onClick={() => createMut.mutate()}
            >
              Continue to confirm
            </button>
          </div>
        </section>
      )}

      {step === 4 && createdId && (
        <section className="rounded-sm border border-border-soft bg-chalk p-5 space-y-4 max-w-xl">
          <p className="text-sm text-slate">
            Confirm sending <strong>{preview?.count ?? 0}</strong> emails
            {sendMode === 'later' ? ` at ${scheduledAt} IST` : ' now'}, in waves of <strong>{batchSize}</strong>
            {pauseMinutes > 0 ? ` with ${pauseMinutes} min between waves` : ' with no pause'}. This cannot be undone once sending starts.
          </p>
          <button
            type="button"
            className="font-mono text-[11px] uppercase bg-mint text-white px-4 py-2.5 rounded-sm disabled:opacity-40"
            disabled={confirmMut.isPending}
            onClick={() => confirmMut.mutate(createdId)}
          >
            Confirm {sendMode === 'later' ? 'schedule' : 'send'}
          </button>
        </section>
      )}
    </div>
  );
}
