import { useCallback, useEffect, useRef, useState } from 'react';
import { Maximize2, Pause, Play } from 'lucide-react';
import {
  buildVimeoPlayerEmbedUrl,
  buildYouTubeEmbedUrl,
  parseVimeoVideoId,
  parseYouTubeVideoId,
  toEmbeddableVideoUrl,
} from '@/lib/videoUrl';

function blockRightClick(e: React.SyntheticEvent) {
  e.preventDefault();
  e.stopPropagation();
}

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
 * Blocks mouse events from reaching the embed iframe so Vimeo/YouTube context menus
 * (Screenshot frame, debug panel, etc.) cannot open. Play/pause via postMessage + bar.
 */
export default function ProtectedVideoEmbed({ videoUrl, title }: ProtectedVideoEmbedProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [playing, setPlaying] = useState(false);
  const [ready, setReady] = useState(false);

  const detected = detectProvider(videoUrl);
  const embedSrc = detected
    ? detected.provider === 'vimeo'
      ? buildVimeoPlayerEmbedUrl(detected.id)
      : buildYouTubeEmbedUrl(detected.id, window.location.origin)
    : toEmbeddableVideoUrl(videoUrl);

  const postToPlayer = useCallback(
    (payload: Record<string, unknown>) => {
      const iframe = iframeRef.current;
      if (!iframe?.contentWindow || !detected) return;
      const targetOrigin =
        detected.provider === 'vimeo' ? 'https://player.vimeo.com' : 'https://www.youtube.com';
      iframe.contentWindow.postMessage(JSON.stringify(payload), targetOrigin);
    },
    [detected],
  );

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      if (!detected) return;
      const allowed =
        detected.provider === 'vimeo'
          ? event.origin === 'https://player.vimeo.com'
          : event.origin === 'https://www.youtube.com';
      if (!allowed) return;

      let data: { event?: string } = {};
      try {
        data = typeof event.data === 'string' ? JSON.parse(event.data) : event.data;
      } catch {
        return;
      }

      if (data.event === 'ready') setReady(true);
      if (data.event === 'play') setPlaying(true);
      if (data.event === 'pause' || data.event === 'finish' || data.event === 'ended') setPlaying(false);
    };

    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [detected]);

  const subscribePlayerEvents = useCallback(() => {
    if (!detected) return;
    if (detected.provider === 'vimeo') {
      (['play', 'pause', 'finish'] as const).forEach((name) => {
        postToPlayer({ method: 'addEventListener', value: name });
      });
      setReady(true);
      return;
    }
    postToPlayer({ event: 'listening' });
    setReady(true);
  }, [detected, postToPlayer]);

  const play = useCallback(() => {
    if (!detected) return;
    if (detected.provider === 'vimeo') {
      postToPlayer({ method: 'play' });
    } else {
      postToPlayer({ event: 'command', func: 'playVideo', args: [] });
    }
    setPlaying(true);
  }, [detected, postToPlayer]);

  const pause = useCallback(() => {
    if (!detected) return;
    if (detected.provider === 'vimeo') {
      postToPlayer({ method: 'pause' });
    } else {
      postToPlayer({ event: 'command', func: 'pauseVideo', args: [] });
    }
    setPlaying(false);
  }, [detected, postToPlayer]);

  const togglePlay = useCallback(() => {
    if (playing) pause();
    else play();
  }, [playing, play, pause]);

  const goFullscreen = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    void (el.requestFullscreen?.() ?? (el as HTMLElement & { webkitRequestFullscreen?: () => void }).webkitRequestFullscreen?.());
  }, []);

  if (!embedSrc) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[280px] text-chalk font-mono text-sm">
        No video link configured.
      </div>
    );
  }

  return (
    <div ref={containerRef} className="relative w-full h-full min-h-[280px] bg-black">
      <iframe
        ref={iframeRef}
        src={embedSrc}
        title={title}
        className="absolute inset-0 h-full w-full border-0 pointer-events-none"
        allow="autoplay; fullscreen; picture-in-picture; encrypted-media"
        onLoad={subscribePlayerEvents}
      />

      {/* Captures all mouse input so the iframe never receives right-click. */}
      <div
        className="absolute inset-0 z-20 cursor-pointer"
        role="presentation"
        onContextMenu={blockRightClick}
        onMouseDown={(e) => {
          if (e.button === 2) blockRightClick(e);
        }}
        onAuxClick={(e) => {
          if (e.button === 2) blockRightClick(e);
        }}
        onClick={() => {
          if (!ready) return;
          togglePlay();
        }}
        onDoubleClick={goFullscreen}
      />

      <div className="absolute bottom-0 left-0 right-0 z-30 flex items-center gap-2 bg-gradient-to-t from-black/80 to-transparent px-3 py-2 pointer-events-auto">
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            togglePlay();
          }}
          className="inline-flex items-center justify-center w-9 h-9 rounded-sm bg-chalk/15 text-chalk hover:bg-chalk/25 border border-chalk/20"
          aria-label={playing ? 'Pause' : 'Play'}
        >
          {playing ? <Pause size={18} /> : <Play size={18} className="ml-0.5" />}
        </button>
        <span className="font-mono text-[10px] text-chalk/70 truncate flex-1">{title}</span>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            goFullscreen();
          }}
          className="inline-flex items-center justify-center w-9 h-9 rounded-sm bg-chalk/15 text-chalk hover:bg-chalk/25 border border-chalk/20"
          aria-label="Fullscreen"
        >
          <Maximize2 size={16} />
        </button>
      </div>
    </div>
  );
}
