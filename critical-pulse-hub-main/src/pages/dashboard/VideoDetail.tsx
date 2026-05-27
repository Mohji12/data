import { useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/apiClient';
import ProtectedVideoEmbed from '@/components/dashboard/ProtectedVideoEmbed';

function blockRightClick(e: React.SyntheticEvent) {
  e.preventDefault();
  e.stopPropagation();
}

/** Block browser context menu on the whole video watch page. */
function useDisablePageRightClick() {
  useEffect(() => {
    const capture = { capture: true };
    const blockMenu = (e: Event) => e.preventDefault();
    const blockSecondary = (e: MouseEvent) => {
      if (e.button === 2) {
        e.preventDefault();
        e.stopPropagation();
      }
    };

    document.addEventListener('contextmenu', blockMenu, capture);
    document.addEventListener('mousedown', blockSecondary, capture);
    document.addEventListener('mouseup', blockSecondary, capture);
    document.addEventListener('auxclick', blockSecondary, capture);

    return () => {
      document.removeEventListener('contextmenu', blockMenu, capture);
      document.removeEventListener('mousedown', blockSecondary, capture);
      document.removeEventListener('mouseup', blockSecondary, capture);
      document.removeEventListener('auxclick', blockSecondary, capture);
    };
  }, []);
}

export default function VideoDetail() {
  const { id } = useParams();

  const { data: video, isLoading, error } = useQuery({
    queryKey: ['video', id],
    queryFn: () => apiClient(`/videos/${id}`),
    enabled: !!id,
  });

  useDisablePageRightClick();

  useEffect(() => {
    if (!video?.video_url || !id) return;
    void apiClient(`/videos/${id}/play-audit`, { method: 'POST', body: '{}' }).catch(() => {});
  }, [video?.video_url, id]);

  return (
    <div className="px-3 py-4 sm:p-6 lg:p-8" onContextMenu={blockRightClick}>
      <Link
        to="/dashboard/videos"
        className="flex items-center gap-2 font-mono text-xs text-ink-faint hover:text-mint mb-6"
      >
        <ArrowLeft size={14} /> Back to Library
      </Link>

      {isLoading && <div className="font-mono text-xs text-ink-faint">Loading video details...</div>}
      {error && (
        <div className="text-red-500 font-sans text-sm">
          Error loading video. It may be unavailable or restricted.
        </div>
      )}

      {video && (
        <>
          <div
            className="bg-monitor-bg rounded-sm w-full aspect-video min-h-[220px] sm:min-h-0 mb-4 sm:mb-6 overflow-hidden -mx-3 sm:mx-0 max-w-[100vw] sm:max-w-none"
            onContextMenu={blockRightClick}
          >
            <ProtectedVideoEmbed videoUrl={video.video_url} title={video.title} />
          </div>
          <h1 className="font-display font-bold text-2xl text-slate mb-2">{video.title}</h1>
          <div className="font-mono text-[11px] text-ink-faint">
            {video.folder_name || 'General'} · Uploaded on {new Date(video.upload_date).toLocaleDateString()}
          </div>
          {(() => {
            if (!video.description) return null;
            // Check if the HTML is actually empty (e.g. `<p>&nbsp;&nbsp;</p>`)
            const stripped = video.description.replace(/<[^>]+>/g, '').replace(/&nbsp;/g, '').trim();
            if (!stripped) return null;
            return (
              <div 
                className="mt-4 font-sans text-sm text-ink-muted [&>p]:mb-2 [&>ul]:list-disc [&>ul]:ml-4 [&>ol]:list-decimal [&>ol]:ml-4"
                dangerouslySetInnerHTML={{ __html: video.description }}
              />
            );
          })()}
        </>
      )}
    </div>
  );
}
