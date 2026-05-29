import { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/apiClient';
import { useIsTechAdmin } from '@/store/authStore';

type OptionRow = { id: number; option_name: string; option_value: string };
type BatchRow = { id: number; name: string; status: string };
type CertificateBatchSettingRow = {
  batch_id: number;
  batch_name: string;
  status: string;
  enabled: boolean;
  certificate_batch_label: string;
  certificate_fixed_date: string;
  certificate_course_line: string;
  certificate_program_line: string;
  certificate_show_date: boolean;
  certificate_name_size: string;
};

const DEFAULT_CERT_NAME_SIZE = '20';

const DEFAULT_CERT_COURSE = 'has completed MASTER CLASSES IN CRITICAL CARE MEDICINE';
const DEFAULT_CERT_PROGRAM =
  'An online education & training program offered by Dr. Harish Mallapura Maheshwarappa';

function splitBatches(raw: string | undefined): string[] {
  return (raw || '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
}

export default function AdminSettings() {
  const qc = useQueryClient();
  const isTech = useIsTechAdmin();
  const [message, setMessage] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const [usdRate, setUsdRate] = useState('');

  const [displayVideo, setDisplayVideo] = useState(false);
  const [accessVideo, setAccessVideo] = useState<string[]>([]);
  const [displayQuiz, setDisplayQuiz] = useState(false);
  const [accessQuiz, setAccessQuiz] = useState<string[]>([]);
  const [displayAuditorium, setDisplayAuditorium] = useState(false);
  const [accessAuditorium, setAccessAuditorium] = useState<string[]>([]);
  const [displayAgenda, setDisplayAgenda] = useState(false);
  const [accessAgenda, setAccessAgenda] = useState<string[]>([]);
  const [displayCertificate, setDisplayCertificate] = useState(false);
  const [accessCertificate, setAccessCertificate] = useState<string[]>([]);
  const [selectedCertBatches, setSelectedCertBatches] = useState<string[]>([]);
  const [certBatchEnabled, setCertBatchEnabled] = useState(false);
  const [certBatchLabel, setCertBatchLabel] = useState('');
  const [certBatchDate, setCertBatchDate] = useState('');
  const [certCourseLine, setCertCourseLine] = useState(DEFAULT_CERT_COURSE);
  const [certProgramLine, setCertProgramLine] = useState(DEFAULT_CERT_PROGRAM);
  const [certShowDate, setCertShowDate] = useState(false);
  const [certNameSize, setCertNameSize] = useState(DEFAULT_CERT_NAME_SIZE);
  const [displayTopupExt, setDisplayTopupExt] = useState(false);
  const [accessTopupExt, setAccessTopupExt] = useState<string[]>([]);
  const [displayTopupExtVideo, setDisplayTopupExtVideo] = useState(false);
  const [accessTopupExtVideo, setAccessTopupExtVideo] = useState<string[]>([]);
  const [accessVideoLink1, setAccessVideoLink1] = useState<string[]>([]);
  const [accessVideoLink2, setAccessVideoLink2] = useState<string[]>([]);
  const [accessVideoLink3, setAccessVideoLink3] = useState<string[]>([]);

  const [agendaTitle, setAgendaTitle] = useState('');
  const [agendaDetails, setAgendaDetails] = useState('');

  const [deactivateBefore, setDeactivateBefore] = useState('');

  const { data: batches } = useQuery({
    queryKey: ['adminMiscBatches'],
    queryFn: () => apiClient('/admin/misc/batches') as Promise<BatchRow[]>,
  });

  const { data: options, isLoading } = useQuery({
    queryKey: ['adminCommerceOptions'],
    queryFn: () => apiClient('/admin/commerce/options') as Promise<OptionRow[]>,
  });
  const { data: certBatchSettings } = useQuery({
    queryKey: ['adminCertificateBatchSettings'],
    queryFn: () => apiClient('/admin/commerce/certificate-batch-settings') as Promise<CertificateBatchSettingRow[]>,
  });
  const activeBatches = (batches || []).filter((b) => String(b.status ?? '1') === '1');
  const certificateBatches = batches || [];

  useEffect(() => {
    if (!options?.length) return;
    const map = new Map<string, string>();
    for (const row of options) {
      if (row.option_name) map.set(row.option_name, row.option_value ?? '');
    }
    setUsdRate(map.get('usd_rate') ?? '');
    setDisplayVideo((map.get('display_video_library_link') || '0') === '1');
    setAccessVideo(splitBatches(map.get('access_video_library_link')));
    setDisplayQuiz((map.get('display_quiz_link') || '0') === '1');
    setAccessQuiz(splitBatches(map.get('access_quiz_link')));
    setDisplayAuditorium((map.get('display_auditorium_link') || '0') === '1');
    setAccessAuditorium(splitBatches(map.get('access_auditorium_link')));
    setDisplayAgenda((map.get('display_agenda') || '0') === '1');
    setAccessAgenda(splitBatches(map.get('access_agenda')));
    setDisplayCertificate((map.get('display_download_certificate') || '0') === '1');
    setAccessCertificate(splitBatches(map.get('access_download_certificate')));
    setDisplayTopupExt((map.get('display_topup_extension_link') || '0') === '1');
    setAccessTopupExt(splitBatches(map.get('access_topup_extension_link')));
    setDisplayTopupExtVideo((map.get('display_topup_extension_link_and_video_library_link') || '0') === '1');
    setAccessTopupExtVideo(splitBatches(map.get('access_topup_extension_link_and_video_library_link')));
    setAccessVideoLink1(splitBatches(map.get('access_video_link')));
    setAccessVideoLink2(splitBatches(map.get('access_video_link_2')));
    setAccessVideoLink3(splitBatches(map.get('access_video_link_3')));
    setAgendaTitle(map.get('agenda_title') ?? '');
    setAgendaDetails(map.get('agenda_details') ?? '');
  }, [options]);

  useEffect(() => {
    if (selectedCertBatches.length === 0) {
      setCertBatchEnabled(false);
      setCertBatchLabel('');
      setCertBatchDate('');
      setCertCourseLine(DEFAULT_CERT_COURSE);
      setCertProgramLine(DEFAULT_CERT_PROGRAM);
      setCertShowDate(false);
      setCertNameSize(DEFAULT_CERT_NAME_SIZE);
      return;
    }
    if (!certBatchSettings) return;
    const firstBatch = selectedCertBatches[0];
    const row = certBatchSettings.find((r) => r.batch_name === firstBatch);
    setCertBatchEnabled(!!row?.enabled);
    setCertBatchLabel(row?.certificate_batch_label || firstBatch);
    setCertBatchDate(row?.certificate_fixed_date || '');
    setCertCourseLine(row?.certificate_course_line || DEFAULT_CERT_COURSE);
    setCertProgramLine(row?.certificate_program_line || DEFAULT_CERT_PROGRAM);
    setCertShowDate(!!row?.certificate_show_date);
    setCertNameSize(row?.certificate_name_size || DEFAULT_CERT_NAME_SIZE);
  }, [selectedCertBatches, certBatchSettings]);

  const upsertMut = useMutation({
    mutationFn: (pair: { option_name: string; option_value: string }) =>
      apiClient('/admin/commerce/options', {
        method: 'POST',
        body: JSON.stringify(pair),
      }),
  });

  const deactivateMut = useMutation({
    mutationFn: (beforeDate: string) =>
      apiClient(`/admin/misc/users/deactivate-before?before_date=${encodeURIComponent(beforeDate)}`, { method: 'POST' }),
  });
  const saveCertBatchMut = useMutation({
    mutationFn: () =>
      apiClient('/admin/commerce/certificate-batch-settings', {
        method: 'POST',
        body: JSON.stringify({
          batch_names: selectedCertBatches,
          enabled: certBatchEnabled,
          certificate_batch_label: certBatchLabel,
          certificate_fixed_date: certBatchDate || null,
          certificate_course_line: certCourseLine,
          certificate_program_line: certProgramLine,
          certificate_show_date: certShowDate,
          certificate_name_size: Number(certNameSize) || 20,
        }),
      }),
  });

  const saveAll = async () => {
    if (!isTech) return;
    setErr(null);
    setMessage(null);
    try {
      const pairs: { option_name: string; option_value: string }[] = [
        { option_name: 'usd_rate', option_value: usdRate.trim() },
        { option_name: 'display_video_library_link', option_value: displayVideo ? '1' : '0' },
        { option_name: 'access_video_library_link', option_value: accessVideo.join(',') },
        { option_name: 'display_quiz_link', option_value: displayQuiz ? '1' : '0' },
        { option_name: 'access_quiz_link', option_value: accessQuiz.join(',') },
        { option_name: 'display_auditorium_link', option_value: displayAuditorium ? '1' : '0' },
        { option_name: 'access_auditorium_link', option_value: accessAuditorium.join(',') },
        { option_name: 'display_agenda', option_value: displayAgenda ? '1' : '0' },
        { option_name: 'access_agenda', option_value: accessAgenda.join(',') },
        { option_name: 'display_download_certificate', option_value: displayCertificate ? '1' : '0' },
        { option_name: 'access_download_certificate', option_value: accessCertificate.join(',') },
        { option_name: 'display_topup_extension_link', option_value: displayTopupExt ? '1' : '0' },
        { option_name: 'access_topup_extension_link', option_value: accessTopupExt.join(',') },
        {
          option_name: 'display_topup_extension_link_and_video_library_link',
          option_value: displayTopupExtVideo ? '1' : '0',
        },
        {
          option_name: 'access_topup_extension_link_and_video_library_link',
          option_value: accessTopupExtVideo.join(','),
        },
        { option_name: 'access_video_link', option_value: accessVideoLink1.join(',') },
        { option_name: 'access_video_link_2', option_value: accessVideoLink2.join(',') },
        { option_name: 'access_video_link_3', option_value: accessVideoLink3.join(',') },
        { option_name: 'agenda_title', option_value: agendaTitle },
        { option_name: 'agenda_details', option_value: agendaDetails },
      ];
      await Promise.all(pairs.map((p) => upsertMut.mutateAsync(p)));
      setMessage('Settings saved.');
      void qc.invalidateQueries({ queryKey: ['adminCommerceOptions'] });
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Save failed');
    }
  };

  const batchSelect = (
    value: string[],
    setValue: (v: string[]) => void,
    options: BatchRow[] = activeBatches,
  ) => {
    const toggleAll = () => {
      if (options.length === 0) return;
      if (value.length === options.length) {
        setValue([]);
      } else {
        setValue(options.map((b) => b.name));
      }
    };

    return (
      <div className="w-full max-w-xl border border-border-soft rounded-sm bg-chalk-warm overflow-hidden shadow-sm">
        {isTech && options.length > 0 && (
          <div className="px-3 py-2 border-b border-border-soft bg-chalk/50 flex justify-between items-center">
            <span className="text-[10px] font-mono text-ink-faint uppercase tracking-tight">
              {value.length} of {options.length} selected
            </span>
            <button
              type="button"
              onClick={toggleAll}
              className="text-[10px] font-mono text-slate hover:text-slate-light font-bold uppercase transition-colors"
            >
              {value.length === options.length ? 'Clear All' : 'Select All'}
            </button>
          </div>
        )}
        <div className="p-3 max-h-[180px] overflow-y-auto">
          {options.length === 0 ? (
            <div className="text-xs text-ink-faint italic py-2">No batches found</div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1">
              {options.map((b) => {
                const isSelected = value.includes(b.name);
                const inactive = String(b.status ?? '1') !== '1';
                return (
                  <label
                    key={b.id}
                    className={`group flex items-center gap-3 font-sans text-sm cursor-pointer py-1.5 px-2 rounded-sm transition-all duration-200 ${
                      isSelected ? 'bg-slate/5 text-slate' : 'text-ink hover:bg-chalk hover:text-slate'
                    }`}
                  >
                    <div className="relative flex items-center justify-center">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        disabled={!isTech}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setValue([...value, b.name]);
                          } else {
                            setValue(value.filter((v) => v !== b.name));
                          }
                        }}
                        className="peer h-4 w-4 appearance-none rounded-sm border border-border-soft bg-chalk transition-all checked:bg-slate checked:border-slate focus:outline-none focus:ring-2 focus:ring-slate/20 disabled:opacity-40"
                      />
                      <svg
                        className="absolute h-3 w-3 text-chalk opacity-0 peer-checked:opacity-100 transition-opacity pointer-events-none"
                        xmlns="http://www.w3.org/2000/svg"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="4"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    </div>
                    <span className="truncate flex-1">
                      {b.name}
                      {inactive && <span className="text-[10px] text-ink-faint ml-1">(inactive)</span>}
                    </span>
                  </label>
                );
              })}
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="p-6 lg:p-8">
      <h1 className="font-display font-bold text-3xl text-slate mb-2">Site options</h1>
      <p className="font-mono text-[11px] text-ink-faint uppercase tracking-wider mb-6">
        Feature flags and batch access (options table). Editing requires tech admin.
      </p>

      {!isTech && (
        <div className="mb-6 rounded-sm border border-amber/30 bg-amber-pale px-4 py-3 font-sans text-sm text-slate">
          You are signed in as a standard admin. These toggles are read-only; the API returns 403 if a non-tech admin tries to save.
        </div>
      )}

      {err && <div className="mb-4 text-sm text-red-600 bg-red-50 border border-red-100 rounded-sm px-4 py-3">{err}</div>}
      {message && <div className="mb-4 text-sm text-slate bg-mint-pale border border-mint/20 rounded-sm px-4 py-3">{message}</div>}

      {isLoading && <div className="font-mono text-xs text-ink-faint animate-pulse py-8">Loading options…</div>}

      <div className="space-y-6 max-w-3xl">
        <section className="bg-chalk border border-border-soft rounded-sm p-6">
          <h2 className="font-display font-bold text-lg text-slate mb-4">USD rate</h2>
          <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">Dollar (USD) rate</label>
          <input
            type="text"
            value={usdRate}
            disabled={!isTech}
            onChange={(e) => setUsdRate(e.target.value)}
            className="w-full max-w-xs bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm disabled:opacity-60"
            placeholder="e.g. 83"
          />
        </section>

        <section className="bg-chalk border border-border-soft rounded-sm p-6">
          <h2 className="font-display font-bold text-lg text-slate mb-4">Video library link</h2>
          <label className="flex items-center gap-3 font-sans text-sm text-ink mb-3">
            <input type="checkbox" checked={displayVideo} disabled={!isTech} onChange={(e) => setDisplayVideo(e.target.checked)} />
            Display video library link
          </label>
          <div className="font-mono text-[10px] text-ink-faint uppercase mb-2">Batches that see the link</div>
          {batchSelect(accessVideo, setAccessVideo)}
        </section>

        <section className="bg-chalk border border-border-soft rounded-sm p-6">
          <h2 className="font-display font-bold text-lg text-slate mb-4">Quiz link</h2>
          <label className="flex items-center gap-3 font-sans text-sm text-ink mb-3">
            <input type="checkbox" checked={displayQuiz} disabled={!isTech} onChange={(e) => setDisplayQuiz(e.target.checked)} />
            Display quiz link
          </label>
          <div className="font-mono text-[10px] text-ink-faint uppercase mb-2">Batches that see the link</div>
          {batchSelect(accessQuiz, setAccessQuiz)}
        </section>

        <section className="bg-chalk border border-border-soft rounded-sm p-6">
          <h2 className="font-display font-bold text-lg text-slate mb-4">Auditorium link</h2>
          <label className="flex items-center gap-3 font-sans text-sm text-ink mb-3">
            <input type="checkbox" checked={displayAuditorium} disabled={!isTech} onChange={(e) => setDisplayAuditorium(e.target.checked)} />
            Display auditorium link
          </label>
          <div className="font-mono text-[10px] text-ink-faint uppercase mb-2">Batches that see the link</div>
          {batchSelect(accessAuditorium, setAccessAuditorium)}
        </section>

        <section className="bg-chalk border border-border-soft rounded-sm p-6">
          <h2 className="font-display font-bold text-lg text-slate mb-4">Agenda</h2>
          <label className="flex items-center gap-3 font-sans text-sm text-ink mb-3">
            <input type="checkbox" checked={displayAgenda} disabled={!isTech} onChange={(e) => setDisplayAgenda(e.target.checked)} />
            Display agenda
          </label>
          <div className="font-mono text-[10px] text-ink-faint uppercase mb-2">Batches that see agenda</div>
          {batchSelect(accessAgenda, setAccessAgenda)}
        </section>

        <section className="bg-chalk border border-border-soft rounded-sm p-6">
          <h2 className="font-display font-bold text-lg text-slate mb-4">Download certificate</h2>
          <label className="flex items-center gap-3 font-sans text-sm text-ink mb-3">
            <input type="checkbox" checked={displayCertificate} disabled={!isTech} onChange={(e) => setDisplayCertificate(e.target.checked)} />
            Display download certificate
          </label>
          <div className="font-mono text-[10px] text-ink-faint uppercase mb-2">Batches that see the link</div>
          {batchSelect(accessCertificate, setAccessCertificate)}

          <div className="mt-6 pt-5 border-t border-border-soft">
            <h3 className="font-display font-bold text-base text-slate mb-3">Per-batch certificate settings</h3>
            <div className="grid gap-4 max-w-xl">
              <div>
                <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">Batches</label>
                {batchSelect(selectedCertBatches, setSelectedCertBatches, certificateBatches)}
                <p className="font-sans text-[10px] text-ink-faint mt-1 italic">
                  Inactive batches (e.g. Batch 14 certificate-only) are included here so you can edit their certificate text.
                </p>
              </div>
              <label className="flex items-center gap-3 font-sans text-sm text-ink">
                <input
                  type="checkbox"
                  checked={certBatchEnabled}
                  disabled={!isTech}
                  onChange={(e) => setCertBatchEnabled(e.target.checked)}
                />
                Enable certificate download for selected batch
              </label>
              <div>
                <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">Recipient name font size</label>
                <input
                  type="number"
                  min={12}
                  max={48}
                  value={certNameSize}
                  disabled={!isTech}
                  onChange={(e) => setCertNameSize(e.target.value)}
                  className="w-full max-w-[140px] bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm disabled:opacity-60"
                />
                <p className="font-sans text-[10px] text-ink-faint mt-1">Default 20. Range 12–48.</p>
              </div>
              <div>
                <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">Certificate batch line</label>
                <input
                  type="text"
                  value={certBatchLabel}
                  disabled={!isTech}
                  onChange={(e) => setCertBatchLabel(e.target.value)}
                  placeholder="e.g. Batch 14 - July to December 2025"
                  className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm disabled:opacity-60"
                />
              </div>
              <div>
                <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">Course completion line</label>
                <input
                  type="text"
                  value={certCourseLine}
                  disabled={!isTech}
                  onChange={(e) => setCertCourseLine(e.target.value)}
                  placeholder={DEFAULT_CERT_COURSE}
                  className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm disabled:opacity-60"
                />
              </div>
              <div>
                <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">Program / offered-by line</label>
                <textarea
                  value={certProgramLine}
                  disabled={!isTech}
                  onChange={(e) => setCertProgramLine(e.target.value)}
                  rows={2}
                  placeholder={DEFAULT_CERT_PROGRAM}
                  className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm disabled:opacity-60"
                />
              </div>
              <label className="flex items-center gap-3 font-sans text-sm text-ink">
                <input
                  type="checkbox"
                  checked={certShowDate}
                  disabled={!isTech}
                  onChange={(e) => setCertShowDate(e.target.checked)}
                />
                Show issue date on certificate
              </label>
              <div>
                <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">Certificate date (optional)</label>
                <input
                  type="date"
                  value={certBatchDate}
                  disabled={!isTech}
                  onChange={(e) => setCertBatchDate(e.target.value)}
                  className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm disabled:opacity-60"
                />
                <p className="font-sans text-[10px] text-ink-faint mt-1">
                  Leave empty to use today&apos;s date when &quot;Show issue date&quot; is enabled.
                </p>
              </div>
              {isTech && (
                <button
                  type="button"
                  onClick={() => {
                    setErr(null);
                    setMessage(null);
                    saveCertBatchMut.mutate(undefined, {
                      onSuccess: () => {
                        setMessage(`Certificate settings saved for ${selectedCertBatches.length} batch(es).`);
                        void qc.invalidateQueries({ queryKey: ['adminCertificateBatchSettings'] });
                      },
                      onError: (e) => setErr(e instanceof Error ? e.message : 'Save failed'),
                    });
                  }}
                  disabled={selectedCertBatches.length === 0 || saveCertBatchMut.isPending}
                  className="magnetic w-fit bg-slate text-chalk rounded-sm px-4 py-2 font-sans text-xs font-semibold hover:bg-slate-light disabled:opacity-50"
                >
                  {saveCertBatchMut.isPending ? 'Saving…' : 'Save batch certificate settings'}
                </button>
              )}
            </div>
          </div>
        </section>

        <section className="bg-chalk border border-border-soft rounded-sm p-6">
          <h2 className="font-display font-bold text-lg text-slate mb-4">Topup extension</h2>
          <label className="flex items-center gap-3 font-sans text-sm text-ink mb-3">
            <input type="checkbox" checked={displayTopupExt} disabled={!isTech} onChange={(e) => setDisplayTopupExt(e.target.checked)} />
            Display topup extension link
          </label>
          <div className="font-mono text-[10px] text-ink-faint uppercase mb-2">Batches</div>
          {batchSelect(accessTopupExt, setAccessTopupExt)}
        </section>

        <section className="bg-chalk border border-border-soft rounded-sm p-6">
          <h2 className="font-display font-bold text-lg text-slate mb-4">Topup extension + video library</h2>
          <label className="flex items-center gap-3 font-sans text-sm text-ink mb-3">
            <input
              type="checkbox"
              checked={displayTopupExtVideo}
              disabled={!isTech}
              onChange={(e) => setDisplayTopupExtVideo(e.target.checked)}
            />
            Display combined link
          </label>
          <div className="font-mono text-[10px] text-ink-faint uppercase mb-2">Batches</div>
          {batchSelect(accessTopupExtVideo, setAccessTopupExtVideo)}
        </section>

        <section className="bg-chalk border border-border-soft rounded-sm p-6">
          <h2 className="font-display font-bold text-lg text-slate mb-4">Extra video links (batch access)</h2>
          <p className="text-xs text-ink-muted mb-4">Matches PHP “Video Link 1 / 2 / 3” batch selectors (`access_video_link`, `_2`, `_3`).</p>
          <div className="space-y-4">
            <div>
              <div className="font-mono text-[10px] text-ink-faint uppercase mb-2">Video link 1</div>
              {batchSelect(accessVideoLink1, setAccessVideoLink1)}
            </div>
            <div>
              <div className="font-mono text-[10px] text-ink-faint uppercase mb-2">Video link 2</div>
              {batchSelect(accessVideoLink2, setAccessVideoLink2)}
            </div>
            <div>
              <div className="font-mono text-[10px] text-ink-faint uppercase mb-2">Video link 3</div>
              {batchSelect(accessVideoLink3, setAccessVideoLink3)}
            </div>
          </div>
        </section>

        <section className="bg-chalk border border-border-soft rounded-sm p-6">
          <h2 className="font-display font-bold text-lg text-slate mb-4">Agenda content</h2>
          <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">Title</label>
          <input
            type="text"
            value={agendaTitle}
            disabled={!isTech}
            onChange={(e) => setAgendaTitle(e.target.value)}
            className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm mb-4 disabled:opacity-60"
          />
          <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">Details (HTML)</label>
          <textarea
            value={agendaDetails}
            disabled={!isTech}
            onChange={(e) => setAgendaDetails(e.target.value)}
            rows={8}
            className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-mono text-xs disabled:opacity-60"
          />
        </section>

        {isTech && (
          <section className="bg-chalk border border-blush/30 rounded-sm p-6">
            <h2 className="font-display font-bold text-lg text-slate mb-2">Bulk deactivate users</h2>
            <p className="font-sans text-xs text-ink-muted mb-4">
              Sets approve = 0 for users created before the given date (YYYY-MM-DD). Use with care.
            </p>
            <div className="flex flex-wrap gap-3 items-end">
              <div>
                <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">Before date</label>
                <input
                  type="date"
                  value={deactivateBefore}
                  onChange={(e) => setDeactivateBefore(e.target.value)}
                  className="bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm"
                />
              </div>
              <button
                type="button"
                disabled={!deactivateBefore || deactivateMut.isPending}
                onClick={() => {
                  if (!window.confirm('Deactivate (unapprove) all users created before this date?')) return;
                  deactivateMut.mutate(deactivateBefore, {
                    onSuccess: (res: { updated?: number }) => {
                      setMessage(`Updated ${res?.updated ?? 0} user(s).`);
                    },
                    onError: (e) => setErr(e instanceof Error ? e.message : 'Request failed'),
                  });
                }}
                className="magnetic bg-blush text-chalk rounded-sm px-4 py-2 font-sans text-xs font-semibold hover:opacity-90 disabled:opacity-50"
              >
                {deactivateMut.isPending ? 'Running…' : 'Deactivate'}
              </button>
            </div>
          </section>
        )}

        {isTech && (
          <button
            type="button"
            onClick={() => void saveAll()}
            disabled={upsertMut.isPending}
            className="magnetic bg-slate text-chalk rounded-sm px-6 py-3 font-sans font-semibold text-sm hover:bg-slate-light disabled:opacity-50"
          >
            {upsertMut.isPending ? 'Saving…' : 'Save settings'}
          </button>
        )}
      </div>
    </div>
  );
}
