export type MailCta = { label: string; url: string };

export type MailTemplate = {
  id: number;
  name: string;
  subject: string;
  preview_text: string;
  hero_image: string;
  hero_image_url?: string;
  body_html: string;
  footer_html: string;
  cta: MailCta[];
  status: string;
  created_at?: string | null;
  updated_at?: string | null;
};

export type MailCampaign = {
  id: number;
  name: string;
  template_id: number;
  subject_override?: string | null;
  preview_text_override?: string | null;
  audience_type: string;
  audience?: Record<string, unknown>;
  status: string;
  scheduled_at?: string | null;
  sent_at?: string | null;
  queued_count: number;
  accepted_count: number;
  failed_count: number;
  suppressed_count: number;
  send_batch_size?: number;
  send_pause_seconds?: number;
  send_pause_minutes?: number;
  next_wave_at?: string | null;
  created_at?: string | null;
  template?: MailTemplate | null;
};

export type MailDashboard = {
  campaigns: number;
  sent: number;
  scheduled: number;
  templates: number;
  default_test_to?: string;
  recent: MailCampaign[];
};

export type AudiencePreview = {
  count: number;
  preview: { email: string; name?: string; batch?: string }[];
  invalid: string[];
  invalid_count: number;
  duplicate_count: number;
};

export type MailAnalytics = {
  campaign: MailCampaign;
  sent: number;
  failed: number;
  unique_opens: number;
  total_clicks: number;
  open_rate: number;
  recent_clicks: { email: string; dest_url: string; at: string | null }[];
};

export function formatIst(iso?: string | null): string {
  if (!iso) return '—';
  const raw = /Z$|[+-]\d{2}:\d{2}$/.test(iso) ? iso : `${iso}Z`;
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('en-IN', {
    timeZone: 'Asia/Kolkata',
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  });
}

export function toIstDatetimeLocal(from?: Date): string {
  const d = from ?? new Date(Date.now() + 60 * 60 * 1000);
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Kolkata',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(d);
  const g = (t: string) => parts.find((p) => p.type === t)?.value || '';
  return `${g('year')}-${g('month')}-${g('day')}T${g('hour')}:${g('minute')}`;
}

export function campaignStatusClass(status: string): string {
  const s = (status || '').toLowerCase();
  if (s === 'sent') return 'bg-mint-pale text-mint border-mint/25';
  if (s === 'scheduled' || s === 'queued' || s === 'sending' || s === 'waiting') return 'bg-amber-pale text-amber-900 border-amber/25';
  if (s === 'failed' || s === 'cancelled') return 'bg-blush/10 text-blush border-blush/25';
  if (s === 'partially_failed') return 'bg-amber-pale text-amber-900 border-amber/25';
  return 'bg-chalk text-slate/70 border-border-soft';
}

export function campaignStatusLabel(row: Pick<MailCampaign, 'status' | 'next_wave_at'>): string {
  const s = (row.status || '').toLowerCase();
  if (s === 'sending' && row.next_wave_at) return 'waiting';
  return (row.status || '').replace(/_/g, ' ');
}
