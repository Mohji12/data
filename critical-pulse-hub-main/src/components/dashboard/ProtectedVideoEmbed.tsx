import {
  buildVimeoPlayerEmbedUrl,
  buildYouTubeEmbedUrl,
  parseVimeoVideoId,
  parseYouTubeVideoId,
  toEmbeddableVideoUrl,
} from '@/lib/videoUrl';

type Provider = 'vimeo' | 'youtube';

function detectProvider(rawUrl?: string | null): { provider: Provider; id: string } | null {
  const vimeoId = parseVimeoVideoId(rawUrl);
  if (vimeoId) return { provider: 'vimeo', id: vimeoId };
  const ytId = parseYouTubeVideoId(rawUrl);
  if (ytId) return { provider: 'youtube', id: ytId };
  return null;
}

type ProtectedVideoEmbedProps = {
  videoUrl?: string | null;
  title: string;
};

/**
 * Renders a fully interactive video player for Vimeo and YouTube.
 * Standard native controls are enabled, including the seek bar, speed adjustment, volume controls,
 * and standard play/pause shortcuts.
 */
export default function ProtectedVideoEmbed({ videoUrl, title }: ProtectedVideoEmbedProps) {
  const detected = detectProvider(videoUrl);
  const embedSrc = detected
    ? detected.provider === 'vimeo'
      ? buildVimeoPlayerEmbedUrl(detected.id)
      : buildYouTubeEmbedUrl(detected.id, window.location.origin)
    : toEmbeddableVideoUrl(videoUrl);

  if (!embedSrc) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[280px] text-chalk font-mono text-sm">
        No video link configured.
      </div>
    );
  }

  return (
    <div 
      className="relative w-full h-full min-h-[280px] bg-black aspect-video rounded overflow-hidden"
      onContextMenu={(e) => {
        e.preventDefault();
        e.stopPropagation();
      }}
    >
      <iframe
        src={embedSrc}
        title={title}
        className="absolute inset-0 h-full w-full border-0"
        allow="autoplay; fullscreen; picture-in-picture; encrypted-media"
      />
    </div>
  );
}
