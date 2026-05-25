import { useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { apiClient } from '@/lib/apiClient';
import { resolvePublicUploadUrl } from '@/lib/apiBase';
import { useIsTechAdmin } from '@/store/authStore';

type BatchRow = {
  id: number;
  name: string;
  status: string;
  display_order: number;
  registration_fee_structure: string | null;
  description: string | null;
  video_url: string | null;
  video_file: string | null;
  video_resolved_url: string | null;
  brochure_file?: string | null;
  brochure_url?: string | null;
  package_subscription?: string | null;
};

type BatchRenameCounts = {
  users?: number;
  packages?: number;
  quiz_exams?: number;
  folder_master?: number;
  videos?: number;
  global_access_options?: number;
  slug_aliases?: number;
};

type BatchUpdateResponse = {
  status: string;
  rename?: BatchRenameCounts;
};

function formatRenameSummary(rename: BatchRenameCounts): string {
  const parts: string[] = [];
  if (rename.users) parts.push(`${rename.users} user(s)`);
  if (rename.packages) parts.push(`${rename.packages} package(s)`);
  if (rename.quiz_exams) parts.push(`${rename.quiz_exams} exam(s)`);
  if (rename.folder_master) parts.push(`${rename.folder_master} folder(s)`);
  if (rename.videos) parts.push(`${rename.videos} video(s)`);
  if (rename.global_access_options) parts.push(`${rename.global_access_options} access option(s)`);
  if (rename.slug_aliases) parts.push(`${rename.slug_aliases} URL alias(es)`);
  if (!parts.length) return 'Batch updated (no linked references needed changes).';
  return `Batch updated — also updated ${parts.join(', ')}.`;
}

export default function AdminBatches() {
  const qc = useQueryClient();
  const isTech = useIsTechAdmin();
  const [name, setName] = useState('');
  const [status, setStatus] = useState<'0' | '1'>('1');
  const [displayOrder, setDisplayOrder] = useState('0');
  const [feeStructure, setFeeStructure] = useState('');
  const [packageSubscription, setPackageSubscription] = useState('');
  const [description, setDescription] = useState('');
  const [videoUrl, setVideoUrl] = useState('');
  const [videoFile, setVideoFile] = useState<string | null>(null);
  const [brochureFile, setBrochureFile] = useState<string | null>(null);
  const [q, setQ] = useState('');
  const [sortBy, setSortBy] = useState<string>('id');
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');
  const [editing, setEditing] = useState<BatchRow | null>(null);
  const [uploadingFor, setUploadingFor] = useState<'new' | number | null>(null);

  const { data: batches, isLoading, error } = useQuery({
    queryKey: ['adminMiscBatches', q, sortBy, order],
    queryFn: () => {
      const p = new URLSearchParams();
      if (q.trim()) p.set('q', q.trim());
      p.set('sort_by', sortBy);
      p.set('order', order);
      return apiClient(`/admin/misc/batches?${p.toString()}`) as Promise<BatchRow[]>;
    },
  });

  const createMut = useMutation({
    mutationFn: () =>
      apiClient('/admin/misc/batches', {
        method: 'POST',
        body: JSON.stringify({
          name: name.trim(),
          status,
          display_order: Number(displayOrder || 0),
          registration_fee_structure: feeStructure.trim() || null,
          package_subscription: packageSubscription.trim() || null,
          description: description.trim() || null,
          video_url: videoUrl.trim() || null,
          video_file: videoFile,
          brochure_file: brochureFile,
        }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['adminMiscBatches'] });
      qc.invalidateQueries({ queryKey: ['regBatchesNavbar'] });
      qc.invalidateQueries({ queryKey: ['registrationCatalogNavbar'] });
      qc.invalidateQueries({ queryKey: ['registrationCatalogNavbarUnified'] });
      qc.invalidateQueries({ queryKey: ['registrationCatalogPublic'] });
      qc.invalidateQueries({ queryKey: ['registrationCatalogCoursesPage'] });
      setName('');
      setStatus('1');
      setDisplayOrder('0');
      setFeeStructure('');
      setPackageSubscription('');
      setDescription('');
      setVideoUrl('');
      setVideoFile(null);
      setBrochureFile(null);
    },
  });

  const updateMut = useMutation({
    mutationFn: (payload: BatchRow) =>
      apiClient(`/admin/misc/batches/${payload.id}`, {
        method: 'PUT',
        body: JSON.stringify({
          name: payload.name.trim(),
          status: payload.status,
          display_order: Number(payload.display_order || 0),
          registration_fee_structure: payload.registration_fee_structure?.trim() || null,
          package_subscription: payload.package_subscription?.trim() || null,
          description: payload.description?.trim() || null,
          video_url: payload.video_url?.trim() || null,
          video_file: payload.video_file?.trim() || null,
          brochure_file: payload.brochure_file?.trim() || null,
        }),
      }) as Promise<BatchUpdateResponse>,
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['adminMiscBatches'] });
      qc.invalidateQueries({ queryKey: ['regBatchesNavbar'] });
      qc.invalidateQueries({ queryKey: ['registrationCatalogNavbar'] });
      qc.invalidateQueries({ queryKey: ['registrationCatalogNavbarUnified'] });
      qc.invalidateQueries({ queryKey: ['registrationCatalogPublic'] });
      qc.invalidateQueries({ queryKey: ['registrationCatalogCoursesPage'] });
      setEditing(null);
      if (data?.rename) {
        toast.success(formatRenameSummary(data.rename));
      } else {
        toast.success('Batch updated.');
      }
    },
    onError: (e: Error) => toast.error(e.message || 'Update failed'),
  });

  const delMut = useMutation({
    mutationFn: (id: number) => apiClient(`/admin/misc/batches/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['adminMiscBatches'] });
      qc.invalidateQueries({ queryKey: ['regBatchesNavbar'] });
      qc.invalidateQueries({ queryKey: ['registrationCatalogNavbar'] });
      qc.invalidateQueries({ queryKey: ['registrationCatalogNavbarUnified'] });
      qc.invalidateQueries({ queryKey: ['registrationCatalogPublic'] });
      qc.invalidateQueries({ queryKey: ['registrationCatalogCoursesPage'] });
    },
  });
  const uploadBrochureMut = useMutation({
    mutationFn: async ({ file }: { file: File }) => {
      const fd = new FormData();
      fd.append('file', file);
      return apiClient('/admin/misc/batches/upload-brochure', {
        method: 'POST',
        body: fd,
      }) as Promise<{ file_name: string; brochure_url: string }>;
    },
  });
  const uploadVideoMut = useMutation({
    mutationFn: async ({ file }: { file: File }) => {
      const fd = new FormData();
      fd.append('file', file);
      return apiClient('/admin/misc/batches/upload-video', {
        method: 'POST',
        body: fd,
      }) as Promise<{ file_name: string; video_url: string }>;
    },
  });
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

  return (
    <div className="p-6 lg:p-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="font-display font-bold text-3xl text-slate">Batches</h1>
          <p className="font-mono text-[11px] text-ink-faint mt-1 uppercase tracking-wider">Registration / access batches (CRUD: tech admin)</p>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder="Search batches..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="bg-chalk border border-border-soft rounded-sm py-2 px-3 font-sans text-sm outline-none focus:border-mint/50 w-64"
          />
          <div className="flex items-center gap-3 font-mono text-[10px] text-ink-faint uppercase tracking-tighter">
            <span>Sort:</span>
            {[
              { id: 'id', label: 'ID' },
              { id: 'name', label: 'Name' },
              { id: 'display_order', label: 'Order' },
            ].map((s) => (
              <button
                key={s.id}
                onClick={() => toggleSort(s.id)}
                className={`hover:text-slate transition-colors ${sortBy === s.id ? 'text-mint font-bold' : ''}`}
              >
                {s.label} {sortBy === s.id ? (order === 'asc' ? '↑' : '↓') : ''}
              </button>
            ))}
          </div>
        </div>
      </div>

      {isTech && (
        <div className="mb-6 flex flex-wrap gap-3 items-end bg-chalk border border-border-soft rounded-sm p-4">
          <div className="flex-1 min-w-[220px]">
            <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">New batch name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm"
              placeholder="e.g. EDIC 2026"
            />
          </div>
          <div className="min-w-[120px]">
            <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">Status</label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as '0' | '1')}
              className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm"
            >
              <option value="1">Active</option>
              <option value="0">Inactive</option>
            </select>
          </div>
          <div className="min-w-[120px]">
            <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">Display order</label>
            <input
              type="number"
              value={displayOrder}
              onChange={(e) => setDisplayOrder(e.target.value)}
              className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm"
            />
          </div>
          <div className="flex-1 min-w-[220px]">
            <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">Fee structure label (optional)</label>
            <input
              value={feeStructure}
              onChange={(e) => setFeeStructure(e.target.value)}
              className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm"
              placeholder="e.g. Practical Series Fee Structure"
            />
          </div>
          <div className="flex-1 min-w-[220px]">
            <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">Package subscription name (optional)</label>
            <input
              value={packageSubscription}
              onChange={(e) => setPackageSubscription(e.target.value)}
              className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm"
              placeholder="e.g. CP 7 — must match package.subscription in DB"
            />
          </div>
          <div className="flex-1 min-w-[300px]">
            <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">Batch Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm min-h-[40px]"
              placeholder="Enter batch description..."
            />
          </div>
          <div className="flex-1 min-w-[220px]">
            <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">Video URL (optional)</label>
            <input
              value={videoUrl}
              onChange={(e) => setVideoUrl(e.target.value)}
              className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm"
              placeholder="e.g. https://youtube.com/..."
            />
          </div>
          <div className="min-w-[240px]">
            <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">Upload Video (optional)</label>
            <input
              type="file"
              accept="video/*"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                const target = e.currentTarget;
                try {
                  setUploadingFor('new');
                  const res = await uploadVideoMut.mutateAsync({ file });
                  setVideoFile(res.file_name);
                } catch (err) {
                  window.alert(err instanceof Error ? err.message : 'Failed to upload video');
                } finally {
                  setUploadingFor(null);
                  if (target) target.value = '';
                }
              }}
              className="w-full bg-chalk-warm border border-border-soft rounded-sm py-1.5 px-2 font-sans text-xs"
            />
            {videoFile && <div className="font-mono text-[10px] text-ink-faint mt-1">{videoFile}</div>}
          </div>
          <div className="min-w-[240px]">
            <label className="font-mono text-[10px] text-ink-faint uppercase block mb-1">Brochure PDF (optional)</label>
            <input
              type="file"
              accept="application/pdf"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                const target = e.currentTarget;
                try {
                  setUploadingFor('new');
                  const res = await uploadBrochureMut.mutateAsync({ file });
                  setBrochureFile(res.file_name);
                } catch (err) {
                  window.alert(err instanceof Error ? err.message : 'Failed to upload brochure');
                } finally {
                  setUploadingFor(null);
                  if (target) target.value = '';
                }
              }}
              className="w-full bg-chalk-warm border border-border-soft rounded-sm py-1.5 px-2 font-sans text-xs"
            />
            {brochureFile && <div className="font-mono text-[10px] text-ink-faint mt-1">{brochureFile}</div>}
          </div>
          <button
            type="button"
            disabled={!name.trim() || createMut.isPending || uploadingFor === 'new'}
            onClick={() => createMut.mutate()}
            className="magnetic bg-slate text-chalk rounded-sm px-4 py-2 font-sans text-xs font-semibold hover:bg-slate-light disabled:opacity-50"
          >
            {createMut.isPending ? 'Adding…' : 'Add batch'}
          </button>
        </div>
      )}

      {isLoading && <div className="font-mono text-xs text-ink-faint py-12 text-center animate-pulse">Loading batches…</div>}
      {error && <div className="text-red-600 font-sans text-sm py-6">Failed to load batches.</div>}

      <div className="space-y-3">
        {(batches || []).map((b) => (
          <div
            key={b.id}
            className="bg-chalk border border-border-soft rounded-sm p-6 flex flex-wrap justify-between items-center gap-4 hover:border-mint/30 transition-all"
          >
            <div>
              <div className="font-display font-bold text-xl text-slate">{b.name}</div>
              <div className="font-mono text-[11px] text-ink-faint mt-1">
                ID #{b.id} · {b.status === '1' ? 'Active' : 'Inactive'} · Display: {b.display_order || 0}
              </div>
              {!!b.registration_fee_structure && (
                <div className="font-mono text-[10px] text-ink-faint mt-1">Fee label: {b.registration_fee_structure}</div>
              )}
              {!!b.package_subscription && (
                <div className="font-mono text-[10px] text-ink-faint mt-1">Packages: {b.package_subscription}</div>
              )}
              {!!b.description && (
                <div className="font-sans text-xs text-slate-light mt-1 max-w-md line-clamp-2">{b.description}</div>
              )}
              {!!b.video_url && (
                <div className="font-mono text-[10px] text-mint mt-1">
                  Link: <a href={b.video_url} target="_blank" rel="noreferrer" className="hover:underline">{b.video_url}</a>
                </div>
              )}
              {!!b.video_resolved_url && (
                <div className="font-mono text-[10px] text-mint mt-1">
                  File: <a href={resolvePublicUploadUrl(b.video_resolved_url) || '#'} target="_blank" rel="noreferrer" className="hover:underline">Play uploaded video</a>
                </div>
              )}
              {!!b.brochure_url && (
                <a
                  href={resolvePublicUploadUrl(b.brochure_url) || '#'}
                  target="_blank"
                  rel="noreferrer"
                  className="font-mono text-[10px] text-mint mt-1 inline-block hover:underline"
                >
                  Open brochure PDF
                </a>
              )}
            </div>
            {isTech ? (
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  className="text-xs text-slate font-sans border border-border-soft rounded-sm px-3 py-1.5 hover:bg-chalk-warm"
                  disabled={updateMut.isPending}
                  onClick={() => setEditing(b)}
                >
                  Edit
                </button>
                <button
                  type="button"
                  className="text-xs text-slate font-sans border border-border-soft rounded-sm px-3 py-1.5 hover:bg-chalk-warm"
                  disabled={updateMut.isPending}
                  onClick={() => updateMut.mutate({ ...b, status: b.status === '1' ? '0' : '1' })}
                >
                  {b.status === '1' ? 'Deactivate' : 'Activate'}
                </button>
                <button
                  type="button"
                  className="text-xs text-blush font-sans border border-blush/30 rounded-sm px-3 py-1.5 hover:bg-blush-pale"
                  disabled={delMut.isPending}
                  onClick={() => {
                    if (window.confirm(`Delete batch "${b.name}"?`)) delMut.mutate(b.id);
                  }}
                >
                  Delete
                </button>
              </div>
            ) : null}
          </div>
        ))}
        {!isLoading && (batches || []).length === 0 && (
          <div className="text-center font-sans text-sm text-ink-muted py-12">No batches.</div>
        )}
      </div>

      {editing && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="w-full max-w-xl bg-chalk border border-border-soft rounded-sm p-5 space-y-3">
            <h3 className="font-display font-bold text-xl text-slate">Edit batch</h3>
            <p className="font-sans text-xs text-ink-muted">
              Renaming updates all enrolled users, exams, videos, and access settings linked to this batch.
            </p>
            <input
              value={editing.name}
              onChange={(e) => setEditing({ ...editing, name: e.target.value })}
              className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm"
              placeholder="Batch name"
            />
            <div className="grid grid-cols-2 gap-3">
              <select
                value={editing.status}
                onChange={(e) => setEditing({ ...editing, status: e.target.value })}
                className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm"
              >
                <option value="1">Active</option>
                <option value="0">Inactive</option>
              </select>
              <input
                type="number"
                value={editing.display_order || 0}
                onChange={(e) => setEditing({ ...editing, display_order: Number(e.target.value || 0) })}
                className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm"
                placeholder="Display order"
              />
            </div>
            <input
              value={editing.registration_fee_structure || ''}
              onChange={(e) => setEditing({ ...editing, registration_fee_structure: e.target.value })}
              className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm"
              placeholder="Fee structure label (optional)"
            />
            <input
              value={editing.package_subscription || ''}
              onChange={(e) => setEditing({ ...editing, package_subscription: e.target.value })}
              className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm"
              placeholder="Package subscription name (e.g. CP 7, CCM Batch 3)"
            />
            <p className="font-sans text-[11px] text-ink-muted -mt-1">
              Display name above is shown on the website. Package subscription must match the batch name in the Packages table.
            </p>
            <textarea
              value={editing.description || ''}
              onChange={(e) => setEditing({ ...editing, description: e.target.value })}
              className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm min-h-[80px]"
              placeholder="Batch description"
            />
            <input
              value={editing.video_url || ''}
              onChange={(e) => setEditing({ ...editing, video_url: e.target.value })}
              className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm"
              placeholder="Video URL (optional)"
            />
            <div className="space-y-2">
              <label className="font-mono text-[10px] text-ink-faint uppercase block">Upload Video (optional)</label>
              <input
                type="file"
                accept="video/*"
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (!file || !editing) return;
                  const target = e.currentTarget;
                  try {
                    setUploadingFor(editing.id);
                    const res = await uploadVideoMut.mutateAsync({ file });
                    setEditing({ ...editing, video_file: res.file_name, video_resolved_url: res.video_url });
                  } catch (err) {
                    window.alert(err instanceof Error ? err.message : 'Failed to upload video');
                  } finally {
                    setUploadingFor(null);
                    if (target) target.value = '';
                  }
                }}
                className="w-full bg-chalk-warm border border-border-soft rounded-sm py-1.5 px-2 font-sans text-xs"
              />
              {editing.video_file && (
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] text-ink-faint">{editing.video_file}</span>
                  <button
                    type="button"
                    className="font-mono text-[10px] text-blush hover:underline"
                    onClick={() => setEditing({ ...editing, video_file: null, video_resolved_url: null })}
                  >
                    Remove
                  </button>
                </div>
              )}
            </div>
            <div className="space-y-2">
              <label className="font-mono text-[10px] text-ink-faint uppercase block">Brochure PDF (optional)</label>
              <input
                type="file"
                accept="application/pdf"
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (!file || !editing) return;
                    const target = e.currentTarget;
                    try {
                      setUploadingFor(editing.id);
                      const res = await uploadBrochureMut.mutateAsync({ file });
                      setEditing({ ...editing, brochure_file: res.file_name, brochure_url: res.brochure_url });
                    } catch (err) {
                      window.alert(err instanceof Error ? err.message : 'Failed to upload brochure');
                    } finally {
                      setUploadingFor(null);
                      if (target) target.value = '';
                    }
                }}
                className="w-full bg-chalk-warm border border-border-soft rounded-sm py-1.5 px-2 font-sans text-xs"
              />
              {editing.brochure_file && (
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] text-ink-faint">{editing.brochure_file}</span>
                  <button
                    type="button"
                    className="font-mono text-[10px] text-blush hover:underline"
                    onClick={() => setEditing({ ...editing, brochure_file: null, brochure_url: null })}
                  >
                    Remove
                  </button>
                </div>
              )}
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" className="px-3 py-2 text-xs border border-border-soft rounded-sm" onClick={() => setEditing(null)}>
                Cancel
              </button>
              <button
                type="button"
                className="px-3 py-2 text-xs bg-slate text-chalk rounded-sm disabled:opacity-50"
                disabled={!editing.name.trim() || updateMut.isPending || uploadingFor === editing.id}
                onClick={() => updateMut.mutate(editing)}
              >
                {updateMut.isPending ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
