import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/apiClient';
import { useIsTechAdmin } from '@/store/authStore';
import { Copy, FolderOpen, MoreVertical, Plus, Pencil, Trash2, Search, X } from 'lucide-react';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

type FolderRow = {
  id: number;
  name: string;
  status?: string | null;
  batch?: string | null;
  display_order?: number | null;
};

type BatchRow = {
  id: number;
  name: string;
  status?: string | null;
};

type BulkCopyPreview = {
  source_batch: string;
  target_batch: string;
  name_from: string;
  name_to: string;
  pair_count: number;
  pairs: {
    source_folder_id: number;
    source_folder_name: string;
    target_folder_id: number;
    target_folder_name: string;
    source_video_count: number;
    target_video_count_before: number;
  }[];
  unmatched_sources: {
    source_folder_id: number;
    source_folder_name: string;
    expected_target_name: string;
    source_video_count: number;
  }[];
  unmatched_targets: { target_folder_id: number; target_folder_name: string }[];
  skipped_same_folder?: {
    folder_id: number;
    folder_name: string;
    expected_target_name: string;
    reason: string;
  }[];
  folders_to_create?: {
    source_folder_id: number;
    source_folder_name: string;
    target_folder_name: string;
    source_video_count: number;
  }[];
  folders_to_create_count?: number;
  name_collisions?: { folder_id: number; folder_name: string; reason: string }[];
};

const emptyBulkForm = () => ({
  source_batch: 'Batch 15',
  target_batch: 'BATCH 16-MCCM',
  name_from: 'B15_',
  name_to: 'B16_',
  add_target_batch_access: true,
  create_missing_folders: true,
  copy_videos: true,
});

const emptyForm = () => ({
  name: '',
  status: '1',
  batch: '',
  display_order: 0,
});

function parseCsvBatches(value: string | null | undefined): string[] {
  if (!value) return [];
  return value
    .split(',')
    .map((v) => v.trim())
    .filter(Boolean);
}

export default function AdminFolders() {
  const qc = useQueryClient();
  const isTech = useIsTechAdmin();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<string>('display_order');
  const [order, setOrder] = useState<'asc' | 'desc'>('asc');
  const [bulkOpen, setBulkOpen] = useState(false);
  const [bulkForm, setBulkForm] = useState(emptyBulkForm);
  const [bulkPreview, setBulkPreview] = useState<BulkCopyPreview | null>(null);
  const [copyOpen, setCopyOpen] = useState(false);
  const [copyTarget, setCopyTarget] = useState<FolderRow | null>(null);
  const [copySourceId, setCopySourceId] = useState<string>('');
  const [copyAddBatch, setCopyAddBatch] = useState(true);

  const { data: folders, isLoading, error } = useQuery({
    queryKey: ['adminFolders', searchQuery, sortBy, order],
    queryFn: () => {
      const p = new URLSearchParams();
      if (searchQuery.trim()) p.set('q', searchQuery.trim());
      p.set('sort_by', sortBy);
      p.set('order', order);
      return apiClient(`/admin/content/folders?${p.toString()}`) as Promise<FolderRow[]>;
    },
  });
  const { data: batches } = useQuery({
    queryKey: ['adminMiscBatches'],
    queryFn: () => apiClient('/admin/misc/batches') as Promise<BatchRow[]>,
  });
  const activeBatches = useMemo(
    () => (batches || []).filter((b) => String(b.status ?? '1') === '1'),
    [batches],
  );
  const selectedBatchNames = useMemo(() => parseCsvBatches(form.batch), [form.batch]);

  const invalidate = () => void qc.invalidateQueries({ queryKey: ['adminFolders'] });

  const saveMut = useMutation({
    mutationFn: async () => {
      const payload = {
        name: form.name.trim(),
        status: form.status || '1',
        batch: form.batch.trim() || null,
        display_order: Number.isFinite(form.display_order) ? Math.max(0, Math.floor(form.display_order)) : 0,
      };
      if (!payload.name) throw new Error('Folder name is required.');
      if (editId != null) {
        return apiClient(`/admin/content/folders/${editId}`, {
          method: 'PUT',
          body: JSON.stringify(payload),
        });
      }
      return apiClient('/admin/content/folders', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    },
    onSuccess: () => {
      toast.success(editId != null ? 'Folder updated' : 'Folder created');
      setDialogOpen(false);
      setEditId(null);
      setForm(emptyForm());
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message || 'Request failed'),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => apiClient(`/admin/content/folders/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      toast.success('Folder deleted');
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message || 'Delete failed'),
  });

  const bulkBatchesValid =
    bulkForm.source_batch.trim().length > 0 &&
    bulkForm.target_batch.trim().length > 0 &&
    bulkForm.source_batch.trim().toLowerCase() !== bulkForm.target_batch.trim().toLowerCase();

  const bulkPreviewMut = useMutation({
    mutationFn: async () => {
      if (!bulkBatchesValid) {
        throw new Error('Copy from and Copy to must be different batches (e.g. Batch 15 → BATCH 16-MCCM).');
      }
      const payload = { ...bulkForm, dry_run: true };
      return apiClient('/admin/content/folders/clone-batch/preview', {
        method: 'POST',
        body: JSON.stringify(payload),
      }) as Promise<BulkCopyPreview>;
    },
    onSuccess: (data) => {
      setBulkPreview(data);
      const createCount = data.folders_to_create_count ?? 0;
      const pairCount = data.pair_count ?? 0;
      if (createCount === 0 && pairCount === 0) {
        toast.warning('Nothing to clone. Check batch selection and B15_/B16_ name prefix.');
      } else {
        toast.success(
          `Will create ${createCount} folder(s), copy videos for ${pairCount + createCount} topic(s) after create.`,
        );
      }
    },
    onError: (e: Error) => toast.error(e.message || 'Preview failed'),
  });

  const bulkApplyMut = useMutation({
    mutationFn: async (dryRun: boolean) => {
      const payload = { ...bulkForm, dry_run: dryRun };
      return apiClient('/admin/content/folders/clone-batch', {
        method: 'POST',
        body: JSON.stringify(payload),
      }) as Promise<{
        dry_run: boolean;
        folders_created: number;
        video_copy?: { totals?: { pairs_processed: number; folder_updated: number } };
      }>;
    },
    onSuccess: (data, dryRun) => {
      const v = data.video_copy?.totals;
      if (dryRun) {
        toast.info(
          `Dry run: ${data.folders_created ?? 0} folder(s), ${v?.folder_updated ?? 0} video link(s) would update.`,
        );
      } else {
        toast.success(
          `Created ${data.folders_created ?? 0} Batch 16 folder(s); linked videos in ${v?.pairs_processed ?? 0} folder(s).`,
        );
        setBulkOpen(false);
        setBulkPreview(null);
        invalidate();
      }
    },
    onError: (e: Error) => toast.error(e.message || 'Bulk copy failed'),
  });

  const copyVideosMut = useMutation({
    mutationFn: async () => {
      if (!copyTarget || !copySourceId) throw new Error('Select source and target folders.');
      const sourceId = Number(copySourceId);
      if (!Number.isFinite(sourceId)) throw new Error('Invalid source folder.');
      return apiClient('/admin/content/folders/copy-videos', {
        method: 'POST',
        body: JSON.stringify({
          source_folder_id: sourceId,
          target_folder_id: copyTarget.id,
          add_target_batch_access: copyAddBatch,
          dry_run: false,
        }),
      }) as Promise<{ videos_matched: number; folder_updated: number }>;
    },
    onSuccess: (data) => {
      toast.success(`Linked ${data.folder_updated} of ${data.videos_matched} video(s) to "${copyTarget?.name}".`);
      setCopyOpen(false);
      setCopyTarget(null);
      setCopySourceId('');
    },
    onError: (e: Error) => toast.error(e.message || 'Copy failed'),
  });

  const openCreate = () => {
    setEditId(null);
    setForm(emptyForm());
    setDialogOpen(true);
  };

  const openEdit = (f: FolderRow) => {
    setEditId(f.id);
    setForm({
      name: f.name || '',
      status: (f.status ?? '1') === '0' ? '0' : '1',
      batch: (f.batch || '').trim(),
      display_order: f.display_order ?? 0,
    });
    setDialogOpen(true);
  };

  const closeDialog = () => {
    setDialogOpen(false);
    setEditId(null);
    setForm(emptyForm());
  };

  const openCopyVideos = (target: FolderRow) => {
    setCopyTarget(target);
    setCopySourceId('');
    setCopyAddBatch(true);
    setCopyOpen(true);
  };

  const closeBulk = () => {
    setBulkOpen(false);
    setBulkPreview(null);
    setBulkForm(emptyBulkForm());
  };

  const allFolders = folders ?? [];
  const sourceFolderOptions = useMemo(
    () => allFolders.filter((f) => f.id !== copyTarget?.id).sort((a, b) => (a.name || '').localeCompare(b.name || '')),
    [allFolders, copyTarget?.id],
  );

  const toggleSort = (field: string) => {
    if (sortBy === field) {
      setOrder(order === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setOrder('asc');
    }
  };

  return (
    <div className="p-6 lg:p-8">
      <Dialog open={bulkOpen} onOpenChange={(o) => !o && closeBulk()}>
        <DialogContent className="bg-chalk border-border-soft sm:max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="font-display text-slate">Clone Batch 15 → Batch 16 (folders + videos)</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-ink-muted">
            Creates all missing <span className="font-mono">B16_</span> folders from Batch 15 (name{' '}
            <span className="font-mono">B15_</span> → <span className="font-mono">B16_</span>), then links every video
            so Batch 16 students see the same library. Does not upload duplicate video files.
          </p>
          {!bulkBatchesValid && (
            <p className="text-sm text-red-600 font-medium">
              Copy from and Copy to must be different. Use Batch 15 (from) and BATCH 16-MCCM (to).
            </p>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 py-2">
            <label className="block">
              <span className="font-mono text-xs text-ink-faint uppercase block mb-1">Copy from batch (has videos)</span>
              <select
                value={bulkForm.source_batch}
                onChange={(e) => {
                  setBulkPreview(null);
                  setBulkForm((x) => ({ ...x, source_batch: e.target.value }));
                }}
                className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm text-ink"
              >
                {activeBatches.map((b) => (
                  <option key={b.id} value={b.name}>
                    {b.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="font-mono text-xs text-ink-faint uppercase block mb-1">Copy to batch (new folders)</span>
              <select
                value={bulkForm.target_batch}
                onChange={(e) => {
                  setBulkPreview(null);
                  setBulkForm((x) => ({ ...x, target_batch: e.target.value }));
                }}
                className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm text-ink"
              >
                {activeBatches.map((b) => (
                  <option key={b.id} value={b.name}>
                    {b.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="font-mono text-xs text-ink-faint uppercase block mb-1">In folder name, replace</span>
              <input
                value={bulkForm.name_from}
                onChange={(e) => setBulkForm((x) => ({ ...x, name_from: e.target.value }))}
                className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm text-ink font-mono"
                placeholder="B15_"
              />
            </label>
            <label className="block">
              <span className="font-mono text-xs text-ink-faint uppercase block mb-1">With</span>
              <input
                value={bulkForm.name_to}
                onChange={(e) => setBulkForm((x) => ({ ...x, name_to: e.target.value }))}
                className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm text-ink font-mono"
                placeholder="B16_"
              />
            </label>
          </div>
          <label className="flex items-center gap-2 text-sm text-ink">
            <input
              type="checkbox"
              checked={bulkForm.create_missing_folders}
              onChange={(e) => {
                setBulkPreview(null);
                setBulkForm((x) => ({ ...x, create_missing_folders: e.target.checked }));
              }}
            />
            Create missing Batch 16 folders from Batch 15 names
          </label>
          <label className="flex items-center gap-2 text-sm text-ink">
            <input
              type="checkbox"
              checked={bulkForm.add_target_batch_access}
              onChange={(e) => setBulkForm((x) => ({ ...x, add_target_batch_access: e.target.checked }))}
            />
            Grant BATCH 16-MCCM access on each video (recommended)
          </label>
          {bulkPreview && (
            <div className="border border-border-soft rounded-sm p-3 max-h-48 overflow-y-auto text-xs space-y-2">
              <p className="font-mono text-ink-faint uppercase">
                {(bulkPreview.folders_to_create_count ?? 0) > 0
                  ? `Will create ${bulkPreview.folders_to_create_count} new folder(s)`
                  : 'No new folders needed'}
                {bulkPreview.pair_count > 0 ? ` · ${bulkPreview.pair_count} already exist` : ''}
                {bulkPreview.unmatched_sources.length > 0
                  ? ` · ${bulkPreview.unmatched_sources.length} unmatched (check B15_/B16_ prefix)`
                  : ''}
              </p>
              {(bulkPreview.folders_to_create?.length ?? 0) > 0 && (
                <div className="text-ink space-y-0.5 pb-1 border-b border-border-soft">
                  <p className="font-semibold text-mint">New folders:</p>
                  {bulkPreview.folders_to_create!.slice(0, 8).map((c) => (
                    <div key={c.source_folder_id}>
                      {c.source_folder_name} → {c.target_folder_name}
                    </div>
                  ))}
                  {(bulkPreview.folders_to_create?.length ?? 0) > 8 && (
                    <div className="text-ink-faint">…and {(bulkPreview.folders_to_create?.length ?? 0) - 8} more</div>
                  )}
                </div>
              )}
              {bulkPreview.pairs.map((p) => (
                <div key={p.source_folder_id} className="text-ink">
                  <span className="text-mint font-semibold">{p.source_folder_name}</span>
                  <span className="text-ink-muted"> → </span>
                  <span className="font-semibold">{p.target_folder_name}</span>
                  <span className="text-ink-faint"> ({p.source_video_count} videos)</span>
                </div>
              ))}
              {bulkPreview.unmatched_sources.slice(0, 5).map((u) => (
                <div key={u.source_folder_id} className="text-amber-700">
                  No target: {u.source_folder_name} (expected &quot;{u.expected_target_name}&quot;)
                </div>
              ))}
              {(bulkPreview.skipped_same_folder?.length ?? 0) > 0 && (
                <div className="text-red-600 space-y-1 pt-1 border-t border-border-soft">
                  <p className="font-semibold">Skipped (same folder — fix batch assignment):</p>
                  {bulkPreview.skipped_same_folder!.slice(0, 5).map((s) => (
                    <div key={s.folder_id}>{s.folder_name}</div>
                  ))}
                </div>
              )}
            </div>
          )}
          <DialogFooter className="gap-2 flex-wrap sm:gap-0">
            <Button type="button" variant="outline" onClick={closeBulk}>
              Cancel
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={bulkPreviewMut.isPending || !bulkBatchesValid}
              onClick={() => bulkPreviewMut.mutate()}
            >
              {bulkPreviewMut.isPending ? 'Previewing…' : 'Preview matches'}
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={!bulkPreview || bulkApplyMut.isPending || !bulkBatchesValid}
              onClick={() => bulkApplyMut.mutate(true)}
            >
              Dry run
            </Button>
            <Button
              type="button"
              className="bg-slate text-chalk hover:bg-slate-light"
              disabled={
                !bulkPreview ||
                bulkApplyMut.isPending ||
                !bulkBatchesValid ||
                ((bulkPreview.folders_to_create_count ?? 0) === 0 && (bulkPreview.pair_count ?? 0) === 0)
              }
              onClick={() => {
                const nCreate = bulkPreview?.folders_to_create_count ?? 0;
                const nVideo = (bulkPreview?.pair_count ?? 0) + nCreate;
                if (
                  !window.confirm(
                    `Create ${nCreate} Batch 16 folder(s) and link videos for ~${nVideo} topic(s)? Video files are reused, not re-uploaded.`,
                  )
                ) {
                  return;
                }
                bulkApplyMut.mutate(false);
              }}
            >
              {bulkApplyMut.isPending ? 'Cloning…' : 'Clone folders + videos'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={copyOpen} onOpenChange={(o) => !o && setCopyOpen(false)}>
        <DialogContent className="bg-chalk border-border-soft sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="font-display text-slate">Copy videos into folder</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-ink-muted">
            Target: <strong className="text-slate">{copyTarget?.name}</strong>
          </p>
          <label className="block py-2">
            <span className="font-mono text-xs text-ink-faint uppercase block mb-1">Copy from folder</span>
            <select
              value={copySourceId}
              onChange={(e) => setCopySourceId(e.target.value)}
              className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm text-ink max-h-40"
            >
              <option value="">Select source folder…</option>
              {sourceFolderOptions.map((f) => (
                <option key={f.id} value={String(f.id)}>
                  {f.name} (#{f.id})
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm text-ink">
            <input
              type="checkbox"
              checked={copyAddBatch}
              onChange={(e) => setCopyAddBatch(e.target.checked)}
            />
            Add target folder batch to each video (student access)
          </label>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button type="button" variant="outline" onClick={() => setCopyOpen(false)}>
              Cancel
            </Button>
            <Button
              type="button"
              className="bg-slate text-chalk hover:bg-slate-light"
              disabled={!copySourceId || copyVideosMut.isPending}
              onClick={() => copyVideosMut.mutate()}
            >
              {copyVideosMut.isPending ? 'Copying…' : 'Copy videos'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={dialogOpen} onOpenChange={(o) => !o && closeDialog()}>
        <DialogContent className="bg-chalk border-border-soft sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="font-display text-slate">{editId != null ? 'Edit folder' : 'New folder'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <label className="block">
              <span className="font-mono text-xs text-ink-faint uppercase block mb-1">Name</span>
              <input
                value={form.name}
                onChange={(e) => setForm((x) => ({ ...x, name: e.target.value }))}
                className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm text-ink"
                placeholder="Folder title"
              />
            </label>
            <label className="block">
              <span className="font-mono text-xs text-ink-faint uppercase block mb-1">Batch (optional)</span>
              <select
                multiple
                value={selectedBatchNames}
                onChange={(e) => {
                  const next = Array.from(e.target.selectedOptions).map((opt) => opt.value);
                  setForm((x) => ({ ...x, batch: next.join(', ') }));
                }}
                className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm text-ink min-h-[110px]"
              >
                {activeBatches.map((b) => (
                  <option key={b.id} value={b.name}>
                    {b.name}
                  </option>
                ))}
              </select>
              <p className="text-xs text-ink-muted mt-1">
                Multi-select supported. Leave unselected for public / all batches. Saved as comma-separated subscription names.
              </p>
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="block">
                <span className="font-mono text-xs text-ink-faint uppercase block mb-1">Display order</span>
                <input
                  type="number"
                  min={0}
                  value={form.display_order}
                  onChange={(e) => setForm((x) => ({ ...x, display_order: Number(e.target.value) || 0 }))}
                  className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm text-ink"
                />
              </label>
              <label className="block">
                <span className="font-mono text-xs text-ink-faint uppercase block mb-1">Status</span>
                <select
                  value={form.status}
                  onChange={(e) => setForm((x) => ({ ...x, status: e.target.value }))}
                  className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm text-ink"
                >
                  <option value="1">Active</option>
                  <option value="0">Inactive</option>
                </select>
              </label>
            </div>
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button type="button" variant="outline" className="border-border-strong" onClick={closeDialog}>
              Cancel
            </Button>
            <Button
              type="button"
              className="bg-slate text-chalk hover:bg-slate-light"
              disabled={saveMut.isPending || !form.name.trim()}
              onClick={() => saveMut.mutate()}
            >
              {saveMut.isPending ? 'Saving…' : editId != null ? 'Save changes' : 'Create folder'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <div className="mb-8 space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
          <div>
            <h1 className="font-display font-bold text-3xl text-slate text-center sm:text-left">Folder Manager</h1>
            <p className="font-mono text-xs text-ink-muted mt-1 uppercase tracking-wider">
              Manage library structure &amp; batch assignments
            </p>
          </div>
          <div className="flex flex-wrap gap-2 shrink-0">
            <button
              type="button"
              disabled={!isTech}
              onClick={() => isTech && (setBulkForm(emptyBulkForm()), setBulkPreview(null), setBulkOpen(true))}
              title={!isTech ? 'Tech admin only' : 'Bulk copy videos from previous batch folders'}
              className="border border-border-strong text-slate rounded-sm px-5 py-3 font-sans text-sm font-semibold hover:bg-chalk-cool transition-all flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Copy size={16} /> Clone Batch 15 → 16
            </button>
            <button
              type="button"
              disabled={!isTech}
              onClick={() => isTech && openCreate()}
              title={!isTech ? 'Folder create/edit/delete requires tech admin' : undefined}
              className="magnetic bg-slate text-chalk rounded-sm px-6 py-3 font-sans text-sm font-semibold hover:bg-slate-light transition-all flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Plus size={16} /> New Folder
            </button>
          </div>
        </div>

        {allFolders.length > 0 && (
          <div className="flex flex-col sm:flex-row sm:items-center gap-4">
            <div className="relative flex-1 min-w-0 max-w-2xl">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate/40 pointer-events-none" aria-hidden />
              <input
                type="search"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search by name or batch…"
                className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2.5 pl-10 pr-10 font-sans text-sm text-slate placeholder:text-slate/40 focus:outline-none focus:ring-2 focus:ring-mint/25 focus:border-mint/35"
                aria-label="Search folders"
              />
              {searchQuery.trim() ? (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded-sm text-slate/50 hover:text-slate hover:bg-chalk-cool"
                  aria-label="Clear search"
                >
                  <X className="h-4 w-4" />
                </button>
              ) : null}
            </div>
            <div className="flex gap-4 font-mono text-[10px] text-ink-faint uppercase tracking-wider items-center">
              <span>Sort:</span>
              {[
                { id: 'display_order', label: 'Order' },
                { id: 'id', label: 'ID' },
                { id: 'name', label: 'Name' },
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
        )}
      </div>

      {isLoading && (
        <div className="font-mono text-xs text-slate/50 py-12 text-center animate-pulse">Loading directory structure...</div>
      )}
      {error && <div className="text-red-500 font-sans text-sm py-12 text-center">Error loading folders.</div>}

      {!isLoading && allFolders.length === 0 && (
        <div className="bg-chalk border border-dashed border-border-strong rounded-sm p-12 text-center">
          <FolderOpen size={48} className="text-slate/25 mx-auto mb-4" />
          <p className="font-sans text-sm text-slate/70">No folders found in the database. Start by creating one.</p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {allFolders.map((f) => (
          <div
            key={f.id}
            className="bg-white border border-border-soft rounded-sm p-6 hover:border-mint/30 hover:shadow-md transition-all group flex flex-col justify-between"
          >
            <div className="flex items-start justify-between mb-4">
              <div className="w-10 h-10 rounded-sm bg-chalk-cool flex items-center justify-center">
                <FolderOpen size={18} className="text-slate group-hover:text-mint transition-colors" />
              </div>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button
                    type="button"
                    disabled={!isTech}
                    title={!isTech ? 'Tech admin only' : 'Folder actions'}
                    className="text-slate/50 hover:text-slate rounded-sm p-1 disabled:opacity-30 outline-none focus-visible:ring-2 focus-visible:ring-mint/40"
                  >
                    <MoreVertical size={16} />
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="bg-chalk border-border-soft">
                  <DropdownMenuItem
                    className="cursor-pointer"
                    disabled={!isTech}
                    onClick={() => isTech && openEdit(f)}
                  >
                    <Pencil className="mr-2 h-4 w-4" />
                    Edit
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    className="cursor-pointer"
                    disabled={!isTech}
                    onClick={() => isTech && openCopyVideos(f)}
                  >
                    <Copy className="mr-2 h-4 w-4" />
                    Copy videos from…
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    className="cursor-pointer text-red-600 focus:text-red-600"
                    disabled={!isTech}
                    onClick={() => {
                      if (!isTech) return;
                      if (!window.confirm(`Delete folder "${f.name}"?`)) return;
                      deleteMut.mutate(f.id);
                    }}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>

            <div className="mb-6">
              <h3 className="font-display font-bold text-lg text-slate group-hover:text-mint transition-colors line-clamp-2" title={f.name}>
                {f.name}
              </h3>
              <div className="flex items-center gap-3 mt-3 flex-wrap">
                  <div className="font-mono text-xs text-ink-muted border border-border-strong rounded-sm px-2 py-0.5 uppercase tracking-tighter">
                    ID #{f.id}
                  </div>
                  <div className="font-mono text-xs text-ink-muted border border-border-strong rounded-sm px-2 py-0.5 uppercase tracking-tighter">
                    Order {f.display_order ?? 0}
                  </div>
              </div>
            </div>

            <div className="pt-4 border-t border-slate-100">
              <div className="font-mono text-xs text-ink-muted uppercase font-bold mb-1">Batch restricted:</div>
              <div className="font-sans text-xs text-slate font-bold line-clamp-2" title={f.batch || 'Public Access'}>
                {f.batch || 'Public Access'}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
