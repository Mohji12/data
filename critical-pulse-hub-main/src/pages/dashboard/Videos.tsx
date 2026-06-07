import { useState } from 'react';
import { Link } from 'react-router-dom';
import { PlayCircle, FolderOpen, ArrowLeft, ChevronLeft, ChevronRight, Search, X } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/apiClient';

const PAGE_SIZE = 12;
const MIN_SEARCH_CHARS = 3;

function buildVideosUrl(params: {
  folderId?: number;
  title?: string;
  page: number;
  pageSize: number;
}) {
  const search = new URLSearchParams();
  search.set('page', String(params.page));
  search.set('page_size', String(params.pageSize));
  if (params.folderId != null) {
    search.set('folder_id', String(params.folderId));
  }
  if (params.title) {
    search.set('title', params.title);
  }
  return `/videos?${search.toString()}`;
}

function VideoSearchBar({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  const trimmed = value.trim();
  const showHint = trimmed.length > 0 && trimmed.length < MIN_SEARCH_CHARS;

  return (
    <div className="mb-6">
      <div className="relative max-w-xl">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint pointer-events-none" />
        <input
          type="search"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder || 'Search videos by name…'}
          className="w-full bg-chalk border border-border-soft rounded-sm py-3 pl-10 pr-10 font-sans text-sm text-ink focus:border-mint/50 outline-none"
          aria-label="Search videos by name"
        />
        {value && (
          <button
            type="button"
            onClick={() => onChange('')}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-faint hover:text-ink cursor-pointer"
            aria-label="Clear search"
          >
            <X size={16} />
          </button>
        )}
      </div>
      {showHint && (
        <p className="font-mono text-[10px] text-ink-faint mt-2 uppercase tracking-wide">
          Type at least {MIN_SEARCH_CHARS} letters to search
        </p>
      )}
    </div>
  );
}

function VideoGrid({
  videos,
  loading,
  error,
  emptyMessage,
}: {
  videos: any[];
  loading: boolean;
  error: unknown;
  emptyMessage: string;
}) {
  if (loading) {
    return <div className="font-mono text-xs text-ink-faint">Loading videos...</div>;
  }
  if (error) {
    return <div className="text-red-500 font-sans text-sm">Error loading videos.</div>;
  }
  if (videos.length === 0) {
    return <p className="font-sans text-sm text-ink-muted col-span-full">{emptyMessage}</p>;
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {videos.map((v: any) => (
        <Link
          key={v.id}
          to={`/dashboard/videos/${v.id}`}
          className="flex items-start gap-4 bg-chalk border border-border-soft rounded-sm p-4 hover:border-mint/30 hover:shadow-sm transition-all group"
        >
          <div className="w-14 h-14 rounded-sm bg-monitor-bg shrink-0 overflow-hidden flex items-center justify-center border border-border-soft">
            {v.thumbnail_url ? (
              <img src={v.thumbnail_url} alt="" className="w-full h-full object-cover" />
            ) : (
              <PlayCircle size={20} className="text-chalk/60" />
            )}
          </div>
          <div className="flex-1 min-w-0">
            <div className="font-sans text-[14px] font-semibold text-ink line-clamp-2 leading-snug">{v.title}</div>
            {v.folder_name && (
              <div className="font-mono text-[9px] text-mint mt-1 uppercase tracking-wide truncate">{v.folder_name}</div>
            )}
            <div className="font-mono text-[10px] text-ink-faint mt-2 uppercase tracking-tight">
              {v.upload_date ? new Date(v.upload_date).toLocaleDateString() : 'Recent'}
            </div>
          </div>
        </Link>
      ))}
    </div>
  );
}

function PaginationControls({
  page,
  hasMore,
  onPageChange,
}: {
  page: number;
  hasMore?: boolean;
  onPageChange: (page: number) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        disabled={page === 1}
        onClick={() => onPageChange(Math.max(1, page - 1))}
        className="p-2 border border-border-soft rounded-sm hover:border-mint/30 disabled:opacity-30 transition-all cursor-pointer"
      >
        <ChevronLeft size={16} />
      </button>
      <span className="font-mono text-xs text-ink px-2">Page {page}</span>
      <button
        type="button"
        disabled={!hasMore}
        onClick={() => onPageChange(page + 1)}
        className="p-2 border border-border-soft rounded-sm hover:border-mint/30 disabled:opacity-30 transition-all cursor-pointer"
      >
        <ChevronRight size={16} />
      </button>
    </div>
  );
}

function PaginationFooter({
  page,
  pageSize,
  total,
  hasMore,
  onPageChange,
}: {
  page: number;
  pageSize: number;
  total: number;
  hasMore?: boolean;
  onPageChange: (page: number) => void;
}) {
  if (total <= pageSize) return null;

  return (
    <div className="flex items-center justify-center gap-4 mt-12 pt-8 border-t border-border-soft">
      <button
        type="button"
        disabled={page === 1}
        onClick={() => {
          onPageChange(Math.max(1, page - 1));
          window.scrollTo(0, 0);
        }}
        className="flex items-center gap-2 px-4 py-2 border border-border-soft rounded-sm hover:bg-chalk-warm disabled:opacity-30 cursor-pointer text-xs font-mono"
      >
        <ChevronLeft size={14} /> Previous
      </button>
      <span className="font-mono text-xs text-ink">Page {page}</span>
      <button
        type="button"
        disabled={!hasMore}
        onClick={() => {
          onPageChange(page + 1);
          window.scrollTo(0, 0);
        }}
        className="flex items-center gap-2 px-4 py-2 border border-border-soft rounded-sm hover:bg-chalk-warm disabled:opacity-30 cursor-pointer text-xs font-mono"
      >
        Next <ChevronRight size={14} />
      </button>
    </div>
  );
}

export default function Videos() {
  const [selectedFolder, setSelectedFolder] = useState<{ id: number; name: string } | null>(null);
  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState('');

  const activeSearch = searchQuery.trim().length >= MIN_SEARCH_CHARS ? searchQuery.trim() : '';

  const handleSearchChange = (value: string) => {
    setSearchQuery(value);
    setPage(1);
  };

  const { data: folders, isLoading: foldersLoading, error: foldersError } = useQuery({
    queryKey: ['videoFolders'],
    queryFn: () => apiClient('/videos/folders'),
  });

  const { data: searchData, isLoading: searchLoading, error: searchError } = useQuery({
    queryKey: ['videosSearch', activeSearch, page],
    queryFn: () =>
      apiClient(
        buildVideosUrl({
          title: activeSearch,
          page,
          pageSize: PAGE_SIZE,
        }),
      ),
    enabled: !!activeSearch && !selectedFolder,
  });

  const { data: videoData, isLoading: videosLoading, error: videosError } = useQuery({
    queryKey: ['videos', selectedFolder?.id, page, activeSearch],
    queryFn: () =>
      apiClient(
        buildVideosUrl({
          folderId: selectedFolder!.id,
          title: activeSearch || undefined,
          page,
          pageSize: PAGE_SIZE,
        }),
      ),
    enabled: !!selectedFolder,
  });

  if (selectedFolder) {
    const videos = videoData?.items || [];
    const hasMore = videoData?.has_more;
    const total = videoData?.total || 0;

    return (
      <div className="p-6 lg:p-8">
        <button
          type="button"
          onClick={() => {
            setSelectedFolder(null);
            setPage(1);
          }}
          className="flex items-center gap-2 font-mono text-xs text-ink-faint hover:text-mint mb-6 cursor-pointer"
        >
          <ArrowLeft size={14} /> Back to Folders
        </button>

        <VideoSearchBar
          value={searchQuery}
          onChange={handleSearchChange}
          placeholder={`Search in ${selectedFolder.name}…`}
        />

        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-8">
          <div>
            <h1 className="font-display font-bold text-3xl text-slate">{selectedFolder.name}</h1>
            <p className="font-mono text-[10px] text-ink-faint mt-1 uppercase tracking-wider">
              {activeSearch
                ? `Search “${activeSearch}” — ${videos.length} of ${total} videos`
                : `Showing ${videos.length} of ${total} videos`}
            </p>
          </div>
          {total > PAGE_SIZE && (
            <PaginationControls page={page} hasMore={hasMore} onPageChange={setPage} />
          )}
        </div>

        <VideoGrid
          videos={videos}
          loading={videosLoading}
          error={videosError}
          emptyMessage={
            activeSearch
              ? `No videos matching “${activeSearch}” in this folder.`
              : 'No videos in this folder for your subscription.'
          }
        />

        <PaginationFooter
          page={page}
          pageSize={PAGE_SIZE}
          total={total}
          hasMore={hasMore}
          onPageChange={setPage}
        />
      </div>
    );
  }

  if (activeSearch) {
    const videos = searchData?.items || [];
    const hasMore = searchData?.has_more;
    const total = searchData?.total || 0;

    return (
      <div className="p-6 lg:p-8">
        <button
          type="button"
          onClick={() => {
            setSearchQuery('');
            setPage(1);
          }}
          className="flex items-center gap-2 font-mono text-xs text-ink-faint hover:text-mint mb-6 cursor-pointer"
        >
          <ArrowLeft size={14} /> Back to Folders
        </button>

        <h1 className="font-display font-bold text-3xl text-slate mb-2">Video Library</h1>
        <VideoSearchBar value={searchQuery} onChange={handleSearchChange} />

        <p className="font-mono text-[10px] text-ink-faint mb-6 uppercase tracking-wider">
          Search results for “{activeSearch}” — {videos.length} of {total} videos
        </p>

        {total > PAGE_SIZE && (
          <PaginationControls page={page} hasMore={hasMore} onPageChange={setPage} />
        )}

        <VideoGrid
          videos={videos}
          loading={searchLoading}
          error={searchError}
          emptyMessage={`No videos matching “${activeSearch}”.`}
        />

        <PaginationFooter
          page={page}
          pageSize={PAGE_SIZE}
          total={total}
          hasMore={hasMore}
          onPageChange={setPage}
        />
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8">
      <h1 className="font-display font-bold text-3xl text-slate mb-2">Video Library</h1>
      <VideoSearchBar value={searchQuery} onChange={handleSearchChange} />

      {foldersLoading && <div className="font-mono text-xs text-ink-faint">Loading folders...</div>}
      {foldersError && (
        <div className="text-red-500 font-sans text-sm">Error loading folders. Please check your connection.</div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {folders && folders.length === 0 && (
          <p className="font-sans text-sm text-ink-muted col-span-full">No video folders available for your subscription.</p>
        )}
        {folders?.map((f: any) => (
          <button
            key={f.id}
            type="button"
            onClick={() => {
              setSelectedFolder({ id: f.id, name: f.name });
              setPage(1);
            }}
            className="flex items-center gap-4 bg-chalk border border-border-soft rounded-sm p-6 hover:border-mint/30 hover:shadow-sm transition-all group text-left cursor-pointer"
          >
            <div className="w-12 h-12 rounded-sm bg-monitor-bg flex items-center justify-center shrink-0">
              <FolderOpen size={20} className="text-mint" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-sans text-[15px] font-medium text-ink truncate">{f.name}</div>
              <div className="font-mono text-[11px] text-ink-faint mt-1 uppercase tracking-wider">Enter Folder</div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
