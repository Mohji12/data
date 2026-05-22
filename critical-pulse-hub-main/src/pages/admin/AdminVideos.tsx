import { useState, useMemo, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/apiClient';
import { openAuthenticatedExport, resolvePublicUploadUrl } from '@/lib/apiBase';
import { useIsTechAdmin } from '@/store/authStore';
import { toast } from 'sonner';
import { Pencil, Trash2, Plus, X, ChevronDown, Search } from 'lucide-react';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';

type VideoAdminRow = {
  id: number;
  title?: string | null;
  description?: string | null;
  folder?: string | null;
  folder_names?: string | null;
  batch?: string | null;
  image?: string | null;
  image_url?: string | null;
  video_link?: string | null;
  upload_date?: string | null;
  status?: string | null;
};

type FolderRow = { id: number; name: string; status?: string | null; batch?: string | null };
type BatchRow = { id: number; name: string; status?: string | null };

type VideoFormState = {
  title: string;
  description: string;
  video_link: string;
  status: string;
  upload_date: string;
  imageFilename: string;
  batchNames: Set<string>;
  folderIds: Set<number>;
};

const emptyForm = (): VideoFormState => ({
  title: '',
  description: '',
  video_link: '',
  status: '1',
  upload_date: new Date().toISOString().slice(0, 10),
  imageFilename: '',
  batchNames: new Set(),
  folderIds: new Set(),
});

function parseCsvInts(s: string | null | undefined): Set<number> {
  const out = new Set<number>();
  if (!s) return out;
  for (const p of s.split(',')) {
    const t = p.trim();
    if (t && /^\d+$/.test(t)) out.add(Number(t));
  }
  return out;
}

function parseCsvStrings(s: string | null | undefined): Set<string> {
  const out = new Set<string>();
  if (!s) return out;
  for (const p of s.split(',')) {
    const t = p.trim();
    if (t) out.add(t);
  }
  return out;
}

/** Folders with no batch are global; otherwise folder.batch is comma-separated batch names (PHP parity). */
function folderMatchesSelectedBatches(folder: FolderRow, selectedBatchNames: Set<string>): boolean {
  const raw = (folder.batch || '').trim();
  if (!raw) return true;
  const parts = raw.split(',').map((x) => x.trim()).filter(Boolean);
  if (selectedBatchNames.size === 0) return false;
  return parts.some((p) => selectedBatchNames.has(p));
}

function MultiSelectBatchesDropdown({
  batches,
  selected,
  onToggle,
}: {
  batches: BatchRow[];
  selected: Set<string>;
  onToggle: (name: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');

  const filteredBatches = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return batches;
    return batches.filter((b) => (b.name || '').toLowerCase().includes(q));
  }, [batches, search]);

  return (
    <Popover
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) setSearch('');
      }}
    >
      <PopoverTrigger asChild>
        <button
          type="button"
          className="flex w-full items-center gap-2 rounded-sm border border-border-soft bg-chalk-warm px-3 py-2 text-left text-sm min-h-[42px] hover:bg-chalk-cool/80"
        >
          <div className="flex min-h-[22px] min-w-0 flex-1 flex-nowrap items-center gap-1 overflow-x-auto overflow-y-hidden [scrollbar-width:thin]">
            {selected.size === 0 ? (
              <span className="text-ink-faint">Select batches…</span>
            ) : (
              [...selected].map((name) => (
                <span
                  key={name}
                  className="inline-flex max-w-[220px] shrink-0 truncate rounded-full bg-mint/15 px-2 py-0.5 font-mono text-[10px] text-slate"
                  title={name}
                >
                  {name}
                </span>
              ))
            )}
          </div>
          <ChevronDown className="h-4 w-4 shrink-0 text-ink-muted" aria-hidden />
        </button>
      </PopoverTrigger>
      <PopoverContent
        className="w-[var(--radix-popover-trigger-width)] max-h-[min(80vh,22rem)] overflow-hidden border-border-soft bg-chalk p-0"
        align="start"
        onOpenAutoFocus={(e) => e.preventDefault()}
      >
        <div className="border-b border-border-soft p-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-faint pointer-events-none" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search batches…"
              className="h-8 pl-8 pr-2 text-xs border-border-soft bg-chalk-warm rounded-sm"
              aria-label="Search batches"
            />
          </div>
        </div>
        <div className="max-h-56 overflow-y-auto p-2">
          {batches.length === 0 ? (
            <p className="px-2 py-4 text-center text-xs text-ink-muted">No batches loaded.</p>
          ) : filteredBatches.length === 0 ? (
            <p className="px-2 py-4 text-center text-xs text-ink-muted">No batches match &quot;{search.trim()}&quot;.</p>
          ) : (
            filteredBatches.map((b) => (
              <label key={b.id} className="flex cursor-pointer items-start gap-2 rounded-sm px-2 py-2 hover:bg-chalk-cool">
                <Checkbox checked={selected.has(b.name)} onCheckedChange={() => onToggle(b.name)} className="mt-0.5" />
                <span className="text-xs leading-snug">{b.name}</span>
              </label>
            ))
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}

function MultiSelectFoldersDropdown({
  folders,
  selectedIds,
  onToggle,
  emptyMessage,
}: {
  folders: FolderRow[];
  selectedIds: Set<number>;
  onToggle: (id: number) => void;
  emptyMessage: string;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');

  const filteredFolders = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return folders;
    return folders.filter((f) => {
      const name = (f.name || '').toLowerCase();
      const batch = (f.batch || '').toLowerCase();
      return name.includes(q) || batch.includes(q);
    });
  }, [folders, search]);

  return (
    <Popover
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) setSearch('');
      }}
    >
      <PopoverTrigger asChild>
        <button
          type="button"
          className="flex w-full items-center gap-2 rounded-sm border border-border-soft bg-chalk-warm px-3 py-2 text-left text-sm min-h-[42px] hover:bg-chalk-cool/80"
        >
          <div className="flex min-h-[22px] min-w-0 flex-1 flex-nowrap items-center gap-1 overflow-x-auto overflow-y-hidden [scrollbar-width:thin]">
            {folders.length === 0 ? (
              <span className="text-ink-faint">{emptyMessage}</span>
            ) : selectedIds.size === 0 ? (
              <span className="text-ink-faint">Select folders (optional)…</span>
            ) : (
              folders
                .filter((f) => selectedIds.has(f.id))
                .map((f) => (
                  <span
                    key={f.id}
                    className="inline-flex max-w-[200px] shrink-0 truncate rounded-full bg-sky-50 px-2 py-0.5 font-mono text-[10px] text-slate"
                    title={f.name}
                  >
                    {f.name}
                  </span>
                ))
            )}
          </div>
          <ChevronDown className="h-4 w-4 shrink-0 text-ink-muted" aria-hidden />
        </button>
      </PopoverTrigger>
      <PopoverContent
        className="w-[var(--radix-popover-trigger-width)] max-h-[min(80vh,22rem)] overflow-hidden border-border-soft bg-chalk p-0"
        align="start"
        onOpenAutoFocus={(e) => e.preventDefault()}
      >
        {folders.length > 0 && (
          <div className="border-b border-border-soft p-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-faint pointer-events-none" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search folder name or batch…"
                className="h-8 pl-8 pr-2 text-xs border-border-soft bg-chalk-warm rounded-sm"
                aria-label="Search folders"
              />
            </div>
          </div>
        )}
        <div className="max-h-56 overflow-y-auto p-2">
          {folders.length === 0 ? (
            <p className="px-2 py-6 text-center text-xs text-ink-muted">{emptyMessage}</p>
          ) : filteredFolders.length === 0 ? (
            <p className="px-2 py-4 text-center text-xs text-ink-muted">No folders match &quot;{search.trim()}&quot;.</p>
          ) : (
            filteredFolders.map((f) => (
              <label key={f.id} className="flex cursor-pointer items-start gap-2 rounded-sm px-2 py-2 hover:bg-chalk-cool">
                <Checkbox checked={selectedIds.has(f.id)} onCheckedChange={() => onToggle(f.id)} className="mt-0.5" />
                <span className="text-xs leading-snug break-words">{f.name}</span>
              </label>
            ))
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}

export default function AdminVideos() {
  const qc = useQueryClient();
  const [q, setQ] = useState('');
  const [batch, setBatch] = useState('');
  const [sortBy, setSortBy] = useState<string>('upload_date');
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');
  const isTech = useIsTechAdmin();
  const [modal, setModal] = useState<'add' | 'edit' | null>(null);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState<VideoFormState>(emptyForm);
  const [localPreview, setLocalPreview] = useState<string | null>(null);

  const { data: videos, isLoading, error } = useQuery({
    queryKey: ['adminVideos', q, batch, sortBy, order],
    queryFn: () => {
      const p = new URLSearchParams();
      if (q.trim()) p.set('q', q.trim());
      if (batch.trim()) p.set('batch', batch.trim());
      p.set('sort_by', sortBy);
      p.set('order', order);
      return apiClient(`/admin/content/videos?${p.toString()}`) as Promise<VideoAdminRow[]>;
    },
  });

  const { data: folders } = useQuery({
    queryKey: ['adminFolders'],
    queryFn: () => apiClient('/admin/content/folders') as Promise<FolderRow[]>,
  });

  const { data: batches } = useQuery({
    queryKey: ['adminMiscBatches'],
    queryFn: () => apiClient('/admin/misc/batches') as Promise<BatchRow[]>,
  });

  const activeFolders = useMemo(
    () => (folders || []).filter((f) => String(f.status ?? '1') === '1'),
    [folders],
  );
  const activeBatches = useMemo(
    () => (batches || []).filter((b) => String(b.status ?? '1') === '1'),
    [batches],
  );

  const foldersForSelectedBatches = useMemo(
    () => activeFolders.filter((f) => folderMatchesSelectedBatches(f, form.batchNames)),
    [activeFolders, form.batchNames],
  );

  const allowedFolderIdSet = useMemo(
    () => new Set(foldersForSelectedBatches.map((f) => f.id)),
    [foldersForSelectedBatches],
  );

  useEffect(() => {
    setForm((f) => {
      const next = new Set([...f.folderIds].filter((id) => allowedFolderIdSet.has(id)));
      if (next.size === f.folderIds.size && [...f.folderIds].every((id) => next.has(id))) return f;
      return { ...f, folderIds: next };
    });
  }, [allowedFolderIdSet]);

  const folderDropdownEmptyMessage =
    foldersForSelectedBatches.length === 0
      ? form.batchNames.size === 0
        ? 'No folders available yet (or only batch-specific folders — select batches below).'
        : 'No folders match the selected batches. Check folder batch assignments in Folder admin.'
      : '';

  const invalidate = () => void qc.invalidateQueries({ queryKey: ['adminVideos'] });

  const uploadThumbMut = useMutation({
    mutationFn: async (file: File) => {
      const fd = new FormData();
      fd.append('file', file);
      return apiClient('/admin/content/videos/upload-image', { method: 'POST', body: fd }) as Promise<{ filename: string }>;
    },
    onSuccess: (res) => {
      setForm((f) => ({ ...f, imageFilename: res.filename }));
      // We keep localPreview if it was set in onChange
      toast.success('Thumbnail uploaded');
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const createMut = useMutation({
    mutationFn: () =>
      apiClient('/admin/content/videos', {
        method: 'POST',
        body: JSON.stringify({
          title: form.title.trim(),
          description: form.description.trim(),
          video_link: form.video_link.trim(),
          image: form.imageFilename.trim(),
          batch: Array.from(form.batchNames).join(','),
          folder:
            form.folderIds.size > 0
              ? Array.from(form.folderIds)
                  .sort((a, b) => a - b)
                  .join(',')
              : null,
          status: form.status,
          upload_date: form.upload_date ? `${form.upload_date}T12:00:00` : undefined,
        }),
      }),
    onSuccess: () => {
      toast.success('Video created');
      setModal(null);
      setForm(emptyForm());
      setLocalPreview(null);
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const updateMut = useMutation({
    mutationFn: () =>
      apiClient(`/admin/content/videos/${editId}`, {
        method: 'PUT',
        body: JSON.stringify({
          title: form.title.trim(),
          description: form.description.trim(),
          video_link: form.video_link.trim(),
          image: form.imageFilename.trim(),
          batch: Array.from(form.batchNames).join(','),
          folder:
            form.folderIds.size > 0
              ? Array.from(form.folderIds)
                  .sort((a, b) => a - b)
                  .join(',')
              : null,
          status: form.status,
          upload_date: form.upload_date ? `${form.upload_date}T12:00:00` : undefined,
        }),
      }),
    onSuccess: () => {
      toast.success('Video updated');
      setModal(null);
      setEditId(null);
      setForm(emptyForm());
      setLocalPreview(null);
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => apiClient(`/admin/content/videos/${id}`, { method: 'DELETE' }),
    onSuccess: () => {
      toast.success('Video deleted');
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const openAdd = () => {
    setForm(emptyForm());
    setEditId(null);
    setModal('add');
  };

  const openEdit = async (id: number) => {
    try {
      const row = (await apiClient(`/admin/content/videos/${id}`)) as {
        title: string;
        description: string;
        video_link: string;
        status: string;
        upload_date: string | null;
        image: string | null;
        batch: string | null;
        folder: string | null;
      };
      setForm({
        title: row.title || '',
        description: row.description || '',
        video_link: row.video_link || '',
        status: row.status || '1',
        upload_date: row.upload_date || new Date().toISOString().slice(0, 10),
        imageFilename: (row.image || '').trim(),
        batchNames: parseCsvStrings(row.batch),
        folderIds: parseCsvInts(row.folder),
      });
      setLocalPreview(null); // Clear any old local preview when editing new record
      setEditId(id);
      setModal('edit');
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to load video');
    }
  };

  const toggleBatch = (name: string) => {
    setForm((f) => {
      const next = new Set(f.batchNames);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return { ...f, batchNames: next };
    });
  };

  const toggleFolder = (id: number) => {
    setForm((f) => {
      const next = new Set(f.folderIds);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return { ...f, folderIds: next };
    });
  };

  const closeModal = () => {
    setModal(null);
    setEditId(null);
    setForm(emptyForm());
    setLocalPreview(null);
  };

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
      {modal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 overflow-y-auto">
          <div className="bg-chalk border border-border-soft rounded-sm shadow-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto p-6 space-y-4 my-8">
            <div className="flex justify-between items-center gap-4">
              <h2 className="font-display font-bold text-xl text-slate">{modal === 'add' ? 'Add video' : 'Edit video'}</h2>
              <button type="button" className="p-1 rounded-sm hover:bg-chalk-cool text-ink-muted" onClick={closeModal} aria-label="Close">
                <X size={20} />
              </button>
            </div>
            <p className="text-xs text-ink-muted">
              Same rules as PHP admin: batches are subscription names (comma-separated). Folders are folder IDs (comma-separated). Set{' '}
              <span className="font-mono">LEGACY_UPLOAD_BASE_URL</span> so thumbnails match <span className="font-mono">/upload/video/image/</span> on the public site.
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block sm:col-span-2">
                <span className="font-mono text-xs text-ink-faint uppercase block mb-1">Title</span>
                <input
                  value={form.title}
                  onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                  className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
                />
              </label>
              <label className="block sm:col-span-2">
                <span className="font-mono text-xs text-ink-faint uppercase block mb-1">Video link</span>
                <input
                  value={form.video_link}
                  onChange={(e) => setForm((f) => ({ ...f, video_link: e.target.value }))}
                  className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
                />
              </label>
              <label className="block sm:col-span-2">
                <span className="font-mono text-xs text-ink-faint uppercase block mb-1">Description</span>
                <textarea
                  value={form.description}
                  onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                  rows={4}
                  className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
                />
              </label>
              <label className="block">
                <span className="font-mono text-xs text-ink-faint uppercase block mb-1">Upload date</span>
                <input
                  type="date"
                  value={form.upload_date}
                  onChange={(e) => setForm((f) => ({ ...f, upload_date: e.target.value }))}
                  className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
                />
              </label>
              <label className="block">
                <span className="font-mono text-xs text-ink-faint uppercase block mb-1">Status</span>
                <select
                  value={form.status}
                  onChange={(e) => setForm((f) => ({ ...f, status: e.target.value }))}
                  className="w-full bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 text-sm"
                >
                  <option value="1">Active</option>
                  <option value="0">Deactive</option>
                </select>
              </label>
            </div>

            <div>
              <span className="font-mono text-xs text-ink-faint uppercase block mb-2">Thumbnail (PNG/JPG/WebP)</span>
              <div className="flex items-start gap-4 p-3 border border-border-soft rounded-sm bg-chalk-warm">
                <div className="w-24 h-16 bg-chalk border border-border-soft rounded-sm overflow-hidden flex-shrink-0 flex items-center justify-center relative group">
                  {localPreview ? (
                    <img src={localPreview} alt="New Preview" className="w-full h-full object-cover" />
                  ) : form.imageFilename ? (
                    <img 
                      src={resolvePublicUploadUrl(`/upload/video/image/${form.imageFilename}`) || ''} 
                      alt="Current" 
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        (e.currentTarget as HTMLImageElement).src = 'https://placehold.co/120x80?text=No+Image';
                      }}
                    />
                  ) : (
                    <div className="text-[10px] text-ink-faint text-center px-1">No Image</div>
                  )}
                  {uploadThumbMut.isPending && (
                    <div className="absolute inset-0 bg-white/60 flex items-center justify-center">
                      <div className="w-4 h-4 border-2 border-mint border-t-transparent rounded-full animate-spin"></div>
                    </div>
                  )}
                </div>
                <div className="flex-1">
                  <input
                    type="file"
                    id="video_thumbnail_input"
                    accept="image/jpeg,image/png,image/webp"
                    disabled={uploadThumbMut.isPending}
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) {
                        const reader = new FileReader();
                        reader.onloadend = () => setLocalPreview(reader.result as string);
                        reader.readAsDataURL(file);
                        uploadThumbMut.mutate(file);
                      }
                      e.target.value = '';
                    }}
                    className="hidden"
                  />
                  <label 
                    htmlFor="video_thumbnail_input" 
                    className={`inline-block px-3 py-1.5 rounded-sm border font-sans text-xs font-bold cursor-pointer transition-all ${
                      uploadThumbMut.isPending 
                      ? 'bg-chalk-cool text-ink-faint border-border-soft' 
                      : 'bg-slate text-chalk border-slate hover:bg-slate-light'
                    }`}
                  >
                    {uploadThumbMut.isPending ? 'Uploading...' : form.imageFilename ? 'Change Image' : 'Select Image'}
                  </label>
                  {form.imageFilename && (
                    <p className="font-mono text-[10px] text-ink-muted mt-2 break-all font-bold">File: {form.imageFilename}</p>
                  )}
                  {!form.imageFilename && !uploadThumbMut.isPending && (
                    <p className="text-[10px] text-red-500 mt-2 font-bold uppercase tracking-tight">Required for new video</p>
                  )}
                </div>
              </div>
            </div>

            <div>
              <span className="font-mono text-xs text-ink-faint uppercase block mb-2">Batches (subscription names)</span>
              <MultiSelectBatchesDropdown batches={activeBatches} selected={form.batchNames} onToggle={toggleBatch} />
              <p className="text-[10px] text-ink-faint mt-1.5">Multi-select. Saved as comma-separated batch names (same as PHP).</p>
            </div>

            <div>
              <span className="font-mono text-xs text-ink-faint uppercase block mb-2">Folders (optional)</span>
              <MultiSelectFoldersDropdown
                folders={foldersForSelectedBatches}
                selectedIds={form.folderIds}
                onToggle={toggleFolder}
                emptyMessage={folderDropdownEmptyMessage}
              />
              <p className="text-[10px] text-ink-faint mt-1.5">
                Folders with no batch in Folder admin are always listed. Others appear when their batch matches your selection above.
              </p>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button type="button" className="px-4 py-2 text-xs font-semibold border border-border-strong rounded-sm hover:bg-chalk-cool" onClick={closeModal}>
                Cancel
              </button>
              <button
                type="button"
                disabled={createMut.isPending || updateMut.isPending}
                className="magnetic bg-slate text-chalk rounded-sm px-4 py-2 font-sans text-xs font-semibold disabled:opacity-50"
                onClick={() => {
                  if (modal === 'add') createMut.mutate();
                  else if (modal === 'edit' && editId != null) updateMut.mutate();
                }}
              >
                {createMut.isPending || updateMut.isPending ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <h1 className="font-display font-bold text-3xl text-slate">Videos</h1>
        <div className="flex flex-wrap gap-2 items-center">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search title…"
            className="bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm min-w-[200px]"
          />
          <select
            value={batch}
            onChange={(e) => setBatch(e.target.value)}
            className="bg-chalk-warm border border-border-soft rounded-sm py-2 px-3 font-sans text-sm min-w-[200px]"
          >
            <option value="">All batches</option>
            {activeBatches.map((b) => (
              <option key={b.id} value={b.name}>
                {b.name}
              </option>
            ))}
          </select>
          {isTech && (
            <button
              type="button"
              onClick={() => void openAuthenticatedExport('/admin/content/video-activity/export.csv')}
              className="magnetic bg-slate text-chalk rounded-sm px-4 py-2 font-sans text-xs font-semibold hover:bg-slate-light"
            >
              Video activity CSV
            </button>
          )}
          {isTech && (
            <button
              type="button"
              onClick={openAdd}
              className="inline-flex items-center gap-1.5 magnetic bg-mint text-slate rounded-sm px-4 py-2 font-sans text-xs font-semibold hover:opacity-90"
            >
              <Plus size={14} /> Add video
            </button>
          )}
          {!isTech && <span className="font-mono text-[10px] text-amber uppercase">View only — tech admin edits</span>}
        </div>
      </div>

      {isLoading && <div className="font-mono text-xs text-ink-faint py-12 text-center animate-pulse">Loading videos…</div>}
      {error && <div className="text-red-600 font-sans text-sm py-6">Failed to load videos.</div>}

      <div className="bg-chalk border border-border-soft rounded-sm overflow-x-auto">
        <table className="w-full min-w-[900px]">
          <thead>
            <tr className="bg-chalk-cool">
              {[
                { label: 'Thumb' },
                { label: 'Batch' },
                { label: 'Folders' },
                { id: 'title', label: 'Title' },
                { id: 'upload_date', label: 'Uploaded' },
                { label: 'Status' },
                { label: 'Actions' },
              ].map((h) => (
                <th
                  key={h.label}
                  onClick={() => 'id' in h && h.id && toggleSort(h.id)}
                  className={`font-mono text-[11px] text-slate/80 uppercase tracking-[0.1em] text-left px-4 py-3 align-bottom ${
                    'id' in h ? 'cursor-pointer hover:text-ink transition-colors' : ''
                  }`}
                >
                  {h.label}
                  {'id' in h && <SortIcon field={h.id!} />}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(videos || []).map((v) => (
              <tr key={v.id} className="border-b border-border-soft hover:bg-ink-ghost">
                <td className="px-4 py-3 w-24 align-top">
                  {v.image_url ? (
                    <img src={v.image_url} alt="" className="w-20 h-14 object-cover rounded-sm border border-border-soft" />
                  ) : (
                    <div className="w-20 h-14 bg-chalk-cool rounded-sm border border-border-soft text-[9px] text-slate/70 font-medium flex items-center justify-center text-center px-1">
                      No preview
                    </div>
                  )}
                </td>
                <td className="px-4 py-3 align-top w-[200px] max-w-[220px]">
                  <p
                    className="font-sans text-xs text-slate leading-relaxed break-words"
                    title={v.batch || undefined}
                  >
                    {v.batch || '—'}
                  </p>
                </td>
                <td className="px-4 py-3 align-top w-[220px] max-w-[260px]">
                  <p
                    className="font-sans text-xs text-slate leading-relaxed break-words"
                    title={v.folder_names || undefined}
                  >
                    {v.folder_names || '—'}
                  </p>
                </td>
                <td className="px-4 py-3 align-top min-w-[200px] max-w-[340px]">
                  <p className="font-sans text-sm font-semibold text-ink leading-snug">{v.title || 'Untitled'}</p>
                </td>
                <td className="px-4 py-3 align-top font-mono text-xs text-slate tabular-nums whitespace-nowrap">
                  {v.upload_date?.slice(0, 10) || '—'}
                </td>
                <td className="px-4 py-3 align-top font-mono text-xs font-bold">
                  <span
                    className={
                      v.status === '1'
                        ? 'text-mint border border-mint/30 bg-mint-pale rounded-full px-2 py-0.5'
                        : 'text-blush border border-blush/30 bg-blush/10 rounded-full px-2 py-0.5'
                    }
                  >
                    {v.status === '1' ? 'Active' : 'Deactive'}
                  </span>
                </td>
                <td className="px-4 py-3 align-top">
                  {isTech ? (
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => void openEdit(v.id)}
                        className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-1 rounded-sm border border-mint/40 text-mint hover:bg-mint/10"
                      >
                        <Pencil size={12} /> Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          if (!window.confirm(`Delete video #${v.id}?`)) return;
                          deleteMut.mutate(v.id);
                        }}
                        className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-1 rounded-sm border border-blush/40 text-blush hover:bg-blush/10"
                      >
                        <Trash2 size={12} /> Delete
                      </button>
                    </div>
                  ) : (
                    <span className="text-[10px] text-ink-faint">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!isLoading && (videos || []).length === 0 && (
          <div className="p-12 text-center font-sans text-sm text-ink-muted">No videos match.</div>
        )}
      </div>
    </div>
  );
}
