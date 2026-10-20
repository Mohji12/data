import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { apiClient } from '@/lib/apiClient';
import { resolveCampaignImageUrl } from '@/lib/apiBase';
import { useIsTechAdmin } from '@/store/authStore';
import MailHtmlEditor from '@/components/admin/MailHtmlEditor';
import AdminMailNav from './AdminMailNav';
import type { MailCta, MailTemplate } from './mailTypes';

type PreviewRes = { subject: string; html: string };

const emptyCta: MailCta = { label: 'Open course', url: 'https://' };

function rewritePreviewHero(html: string, filename: string, displayUrl: string): string {
  if (!html) return html;
  const local = displayUrl || resolveCampaignImageUrl(filename) || '';
  if (!local) return html;
  return html.replace(/https?:\/\/[^"'>\s]+\/upload\/campaigns\/[^"'>\s]+/gi, local);
}

export default function AdminMailTemplateEditor() {
  const { id } = useParams();
  const isNew = !id || id === 'new';
  const templateId = isNew ? null : Number(id);
  const isTech = useIsTechAdmin();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const [name, setName] = useState('');
  const [subject, setSubject] = useState('');
  const [previewText, setPreviewText] = useState('');
  const [heroImage, setHeroImage] = useState('');
  const [heroUrl, setHeroUrl] = useState('');
  const [heroUploading, setHeroUploading] = useState(false);
  const [bodyHtml, setBodyHtml] = useState('<p>Hello {{name}},</p>');
  const [footerHtml, setFooterHtml] = useState('<p>Critical Care Classes</p>');
  const [cta, setCta] = useState<MailCta[]>([{ ...emptyCta }]);
  const [testTo, setTestTo] = useState('');
  const [previewHtml, setPreviewHtml] = useState('');
  const [previewSubject, setPreviewSubject] = useState('');
  const [device, setDevice] = useState<'desktop' | 'mobile'>('desktop');

  const existing = useQuery({
    queryKey: ['adminMailTemplate', templateId],
    queryFn: () => apiClient(`/admin/mail/templates/${templateId}`) as Promise<MailTemplate>,
    enabled: templateId != null && Number.isFinite(templateId),
  });

  useEffect(() => {
    const row = existing.data;
    if (!row) return;
    setName(row.name);
    setSubject(row.subject);
    setPreviewText(row.preview_text || '');
    setHeroImage(row.hero_image || '');
    setHeroUrl(resolveCampaignImageUrl(row.hero_image || row.hero_image_url) || '');
    setBodyHtml(row.body_html || '');
    setFooterHtml(row.footer_html || '');
    setCta(row.cta?.length ? row.cta : [{ ...emptyCta }]);
  }, [existing.data]);

  useEffect(() => {
    if (!existing.data) return;
    const hero = existing.data.hero_image || '';
    const timer = window.setTimeout(() => previewMut.mutate(hero), 80);
    return () => window.clearTimeout(timer);
    // Preview once the saved template (including hero filename) is loaded.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [existing.data]);

  const payload = () => ({
    name,
    subject,
    preview_text: previewText,
    hero_image: heroImage,
    body_html: bodyHtml,
    footer_html: footerHtml,
    cta: cta.filter((c) => c.label.trim() && c.url.trim()),
    status: '1',
  });

  const previewMut = useMutation({
    mutationFn: (heroOverride?: string) => {
      const hero = (heroOverride || heroImage || '').trim();
      return apiClient('/admin/mail/templates/preview', {
        method: 'POST',
        body: JSON.stringify({
          ...payload(),
          hero_image: resolveCampaignImageUrl(hero) || hero,
          name: 'Dr. Sample',
          email: 'doctor@example.com',
          batch: 'Batch 15',
        }),
      }) as Promise<PreviewRes>;
    },
    onSuccess: (res) => {
      setPreviewHtml(res.html);
      setPreviewSubject(res.subject);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const saveMut = useMutation({
    mutationFn: () => {
      if (templateId) {
        return apiClient(`/admin/mail/templates/${templateId}`, {
          method: 'PUT',
          body: JSON.stringify(payload()),
        }) as Promise<MailTemplate>;
      }
      return apiClient('/admin/mail/templates', {
        method: 'POST',
        body: JSON.stringify(payload()),
      }) as Promise<MailTemplate>;
    },
    onSuccess: (row) => {
      toast.success('Template saved');
      setHeroImage(row.hero_image || '');
      setHeroUrl(resolveCampaignImageUrl(row.hero_image || row.hero_image_url) || '');
      void qc.invalidateQueries({ queryKey: ['adminMailTemplates'] });
      void qc.invalidateQueries({ queryKey: ['adminMailTemplate', row.id] });
      previewMut.mutate(row.hero_image || '');
      if (isNew) navigate(`/admin/mail/templates/${row.id}`, { replace: true });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const testMut = useMutation({
    mutationFn: () => {
      if (!templateId) throw new Error('Save the template before sending a test');
      if (!testTo.trim() || !testTo.includes('@')) throw new Error('Enter a test email address');
      return apiClient(`/admin/mail/templates/${templateId}/test-send`, {
        method: 'POST',
        body: JSON.stringify({ ...payload(), to_email: testTo.trim() }),
      });
    },
    onSuccess: () => toast.success('Test email sent'),
    onError: (e: Error) => toast.error(e.message),
  });

  const uploadHero = async (file: File) => {
    const localPreview = URL.createObjectURL(file);
    setHeroUrl(localPreview);
    setHeroUploading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = (await apiClient('/admin/mail/templates/image', { method: 'POST', body: fd })) as {
        filename: string;
        url: string;
      };
      setHeroImage(res.filename);
      const served = resolveCampaignImageUrl(res.filename) || res.url;
      setHeroUrl(served);
      URL.revokeObjectURL(localPreview);
      previewMut.mutate(res.filename);
    } finally {
      setHeroUploading(false);
    }
  };

  const field = 'w-full bg-chalk-warm border border-border-soft rounded-sm py-2.5 px-3 font-sans text-sm text-slate focus:outline-none focus:ring-2 focus:ring-mint/25 focus:border-mint/40';

  return (
    <div className="p-6 lg:p-8 min-w-0 max-w-full">
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-6 mb-6">
        <div>
          <h1 className="font-display font-bold text-3xl text-slate">{isNew ? 'New template' : 'Edit template'}</h1>
          <p className="font-mono text-[11px] text-slate/55 mt-1.5 uppercase tracking-[0.14em]">
            Use {'{{name}}'}, {'{{email}}'}, {'{{batch}}'}
          </p>
        </div>
        <Link to="/admin/mail/templates" className="font-mono text-[11px] uppercase tracking-wider border border-border-soft px-4 py-2.5 rounded-sm">
          Back
        </Link>
      </div>
      <AdminMailNav />

      {!isTech && (
        <div className="text-sm text-amber-900 mb-6 bg-amber-pale border border-amber/25 rounded-sm px-4 py-3">
          Read-only. Tech admin can save and send tests.
        </div>
      )}

      <div className="grid lg:grid-cols-2 gap-6">
        <section className="rounded-sm border border-border-soft bg-chalk p-5 space-y-4">
          <label className="block">
            <span className="font-mono text-[10px] text-slate/65 uppercase tracking-wider block mb-2">Name</span>
            <input className={field} value={name} onChange={(e) => setName(e.target.value)} disabled={!isTech} />
          </label>
          <label className="block">
            <span className="font-mono text-[10px] text-slate/65 uppercase tracking-wider block mb-2">Subject</span>
            <input className={field} value={subject} onChange={(e) => setSubject(e.target.value)} disabled={!isTech} />
          </label>
          <label className="block">
            <span className="font-mono text-[10px] text-slate/65 uppercase tracking-wider block mb-2">Preview text</span>
            <input className={field} value={previewText} onChange={(e) => setPreviewText(e.target.value)} disabled={!isTech} />
          </label>
          <div>
            <span className="font-mono text-[10px] text-slate/65 uppercase tracking-wider block mb-2">Hero image</span>
            {(heroUrl || heroImage) && (
              <img
                src={heroUrl || resolveCampaignImageUrl(heroImage) || ''}
                alt="Hero"
                className="mb-2 max-h-40 w-full object-cover rounded-sm border border-border-soft bg-chalk-warm"
              />
            )}
            {isTech && (
              <input
                type="file"
                accept="image/png,image/jpeg,image/jpg,image/webp"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void uploadHero(file).catch((err: Error) => toast.error(err.message));
                }}
              />
            )}
            {heroUploading && <p className="font-mono text-[10px] text-slate/50 mt-1">Uploading image…</p>}
          </div>
          <div>
            <span className="font-mono text-[10px] text-slate/65 uppercase tracking-wider block mb-2">Body</span>
            <MailHtmlEditor value={bodyHtml} onChange={setBodyHtml} disabled={!isTech} />
          </div>
          <div>
            <span className="font-mono text-[10px] text-slate/65 uppercase tracking-wider block mb-2">Footer</span>
            <MailHtmlEditor value={footerHtml} onChange={setFooterHtml} disabled={!isTech} minHeightClass="min-h-[100px]" />
          </div>
          {cta.map((item, idx) => (
            <div key={idx} className="grid sm:grid-cols-2 gap-3">
              <input
                className={field}
                placeholder="CTA label"
                value={item.label}
                disabled={!isTech}
                onChange={(e) => setCta((rows) => rows.map((r, i) => (i === idx ? { ...r, label: e.target.value } : r)))}
              />
              <input
                className={field}
                placeholder="https://…"
                value={item.url}
                disabled={!isTech}
                onChange={(e) => setCta((rows) => rows.map((r, i) => (i === idx ? { ...r, url: e.target.value } : r)))}
              />
            </div>
          ))}
          {isTech && (
            <div className="flex flex-wrap gap-2 pt-2">
              <button
                type="button"
                className="font-mono text-[11px] uppercase tracking-wider bg-slate text-chalk px-4 py-2.5 rounded-sm disabled:opacity-50"
                disabled={saveMut.isPending || heroUploading}
                onClick={() => saveMut.mutate()}
              >
                Save
              </button>
              <button
                type="button"
                className="font-mono text-[11px] uppercase tracking-wider border border-border-soft px-4 py-2.5 rounded-sm"
                onClick={() => previewMut.mutate()}
              >
                Preview
              </button>
            </div>
          )}
          {isTech && templateId && (
            <div className="flex flex-col sm:flex-row gap-2 pt-2 border-t border-border-soft">
              <input
                className={field}
                placeholder="Test send to…"
                value={testTo}
                onChange={(e) => setTestTo(e.target.value)}
              />
              <button
                type="button"
                className="font-mono text-[11px] uppercase tracking-wider border border-mint/30 bg-mint-pale text-mint px-4 py-2.5 rounded-sm"
                disabled={testMut.isPending}
                onClick={() => testMut.mutate()}
              >
                Test send
              </button>
            </div>
          )}
        </section>

        <section className="rounded-sm border border-border-soft bg-chalk-cool/40 p-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-display font-bold text-lg text-slate">Preview</h2>
            <div className="flex gap-2">
              {(['desktop', 'mobile'] as const).map((d) => (
                <button
                  key={d}
                  type="button"
                  className={`font-mono text-[10px] uppercase px-2.5 py-1 rounded-sm border ${
                    device === d ? 'bg-slate text-chalk border-slate' : 'border-border-soft'
                  }`}
                  onClick={() => setDevice(d)}
                >
                  {d}
                </button>
              ))}
            </div>
          </div>
          <p className="font-mono text-[11px] text-slate/55 mb-3">{previewSubject || subject || 'Subject'}</p>
          <div className="mx-auto bg-white border border-border-soft overflow-hidden" style={{ maxWidth: device === 'mobile' ? 375 : 600 }}>
            <iframe
              title="Email preview"
              srcDoc={
                rewritePreviewHero(previewHtml, heroImage, heroUrl) ||
                '<p style="padding:16px;font-family:sans-serif;color:#6b7280">Click Preview</p>'
              }
              className="w-full min-h-[520px] bg-white"
            />
          </div>
        </section>
      </div>
    </div>
  );
}
