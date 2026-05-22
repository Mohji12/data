import { useState } from 'react';
import { Link } from 'react-router-dom';
import { PlayCircle, FolderOpen, ArrowLeft, ChevronLeft, ChevronRight } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/apiClient';

export default function Videos() {
  const [selectedFolder, setSelectedFolder] = useState<{ id: number; name: string } | null>(null);
  const [page, setPage] = useState(1);
  const pageSize = 12;

  // Step 1: Fetch folders
  const { data: folders, isLoading: foldersLoading, error: foldersError } = useQuery({
    queryKey: ['videoFolders'],
    queryFn: () => apiClient('/videos/folders'),
  });

  // Step 2: When a folder is selected, fetch videos in that folder (Paginated)
  const { data: videoData, isLoading: videosLoading, error: videosError } = useQuery({
    queryKey: ['videos', selectedFolder?.id, page],
    queryFn: () => apiClient(`/videos?folder_id=${selectedFolder?.id}&page=${page}&page_size=${pageSize}`),
    enabled: !!selectedFolder,
  });

  // If a folder is selected, show videos inside it
  if (selectedFolder) {
    const videos = videoData?.items || [];
    const hasMore = videoData?.has_more;
    const total = videoData?.total || 0;

    return (
      <div className="p-6 lg:p-8">
        <button
          onClick={() => { setSelectedFolder(null); setPage(1); }}
          className="flex items-center gap-2 font-mono text-xs text-ink-faint hover:text-mint mb-6 cursor-pointer"
        >
          <ArrowLeft size={14} /> Back to Folders
        </button>
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-8">
          <div>
            <h1 className="font-display font-bold text-3xl text-slate">{selectedFolder.name}</h1>
            <p className="font-mono text-[10px] text-ink-faint mt-1 uppercase tracking-wider">
               Showing {videos.length} of {total} videos
            </p>
          </div>
          
          {/* Pagination Controls */}
          {total > pageSize && (
            <div className="flex items-center gap-2">
               <button 
                 disabled={page === 1}
                 onClick={() => setPage(p => Math.max(1, p - 1))}
                 className="p-2 border border-border-soft rounded-sm hover:border-mint/30 disabled:opacity-30 transition-all cursor-pointer"
               >
                 <ChevronLeft size={16} />
               </button>
               <span className="font-mono text-xs text-ink px-2">Page {page}</span>
               <button 
                 disabled={!hasMore}
                 onClick={() => setPage(p => p + 1)}
                 className="p-2 border border-border-soft rounded-sm hover:border-mint/30 disabled:opacity-30 transition-all cursor-pointer"
               >
                 <ChevronRight size={16} />
               </button>
            </div>
          )}
        </div>

        {videosLoading && <div className="font-mono text-xs text-ink-faint">Loading videos...</div>}
        {videosError && <div className="text-red-500 font-sans text-sm">Error loading videos.</div>}

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {videos.length === 0 && !videosLoading && (
            <p className="font-sans text-sm text-ink-muted col-span-full">No videos in this folder for your subscription.</p>
          )}
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
                <div className="font-mono text-[10px] text-ink-faint mt-2 uppercase tracking-tight">
                   {v.upload_date ? new Date(v.upload_date).toLocaleDateString() : 'Recent'}
                </div>
              </div>
            </Link>
          ))}
        </div>

        {/* Bottom Pagination */}
        {total > pageSize && (
            <div className="flex items-center justify-center gap-4 mt-12 pt-8 border-t border-border-soft">
               <button 
                 disabled={page === 1}
                 onClick={() => { setPage(p => Math.max(1, p - 1)); window.scrollTo(0, 0); }}
                 className="flex items-center gap-2 px-4 py-2 border border-border-soft rounded-sm hover:bg-chalk-warm disabled:opacity-30 cursor-pointer text-xs font-mono"
               >
                 <ChevronLeft size={14} /> Previous
               </button>
               <span className="font-mono text-xs text-ink">Page {page}</span>
               <button 
                 disabled={!hasMore}
                 onClick={() => { setPage(p => p + 1); window.scrollTo(0, 0); }}
                 className="flex items-center gap-2 px-4 py-2 border border-border-soft rounded-sm hover:bg-chalk-warm disabled:opacity-30 cursor-pointer text-xs font-mono"
               >
                 Next <ChevronRight size={14} />
               </button>
            </div>
          )}
      </div>
    );
  }

  // Default: Show folder list
  return (
    <div className="p-6 lg:p-8">
      <h1 className="font-display font-bold text-3xl text-slate mb-8">Video Library</h1>

      {foldersLoading && <div className="font-mono text-xs text-ink-faint">Loading folders...</div>}
      {foldersError && <div className="text-red-500 font-sans text-sm">Error loading folders. Please check your connection.</div>}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {folders && folders.length === 0 && (
          <p className="font-sans text-sm text-ink-muted col-span-full">No video folders available for your subscription.</p>
        )}
        {folders?.map((f: any) => (
          <button
            key={f.id}
            onClick={() => { setSelectedFolder({ id: f.id, name: f.name }); setPage(1); }}
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
