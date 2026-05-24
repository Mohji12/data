import { useEffect, useRef, useCallback, useState } from 'react';
import { Maximize2, Minimize2, Play, Pause, Settings, FastForward, Volume2, VolumeX } from 'lucide-react';
import { resolvePublicUploadUrl } from '@/lib/apiBase';
import {
  buildVimeoPlayerEmbedUrl,
  buildYouTubeEmbedUrl,
  isDirectVideoFileUrl,
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

/** Format seconds as M:SS or H:MM:SS. */
function formatTime(seconds: number): string {
  if (!seconds || !isFinite(seconds)) return '0:00';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

/** Block right-click context menus on the video page at all times. */
function useBlockRightClick() {
  useEffect(() => {
    const block = (e: Event) => {
      e.preventDefault();
      e.stopPropagation();
      return false;
    };
    const blockSecondary = (e: MouseEvent) => {
      if (e.button === 2) {
        e.preventDefault();
        e.stopPropagation();
      }
    };

    const opts = { capture: true };
    document.addEventListener('contextmenu', block, opts);
    document.addEventListener('mousedown', blockSecondary, opts);
    document.addEventListener('mouseup', blockSecondary, opts);
    document.addEventListener('auxclick', blockSecondary, opts);

    return () => {
      document.removeEventListener('contextmenu', block, opts);
      document.removeEventListener('mousedown', blockSecondary, opts);
      document.removeEventListener('mouseup', blockSecondary, opts);
      document.removeEventListener('auxclick', blockSecondary, opts);
    };
  }, []);
}

/**
 * Protected video player with custom controls overlay.
 *
 * A full-area overlay covers the iframe at ALL times (pointer-events never
 * toggled off). Playback, seeking, and fullscreen are handled via postMessage
 * to the Vimeo Player API / YouTube IFrame API.
 *
 * Custom controls rendered on the overlay:
 *  - Play/pause button
 *  - Seek bar (click + drag)
 *  - Time display (current / duration)
 *  - Quality settings
 *  - Playback speed settings
 *  - Fullscreen button
 *  - Keyboard: ← → = ±10s, Space = play/pause, F = fullscreen
 */
export default function ProtectedVideoEmbed({ videoUrl, title }: ProtectedVideoEmbedProps) {
  useBlockRightClick();

  const containerRef = useRef<HTMLDivElement>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const seekBarRef = useRef<HTMLDivElement>(null);
  const clickTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const currentSpeedRef = useRef(1);
  const playerReadyRef = useRef(false);

  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isSeeking, setIsSeeking] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  
  const [qualities, setQualities] = useState<{ id: string; label: string }[]>([]);
  const [currentQuality, setCurrentQuality] = useState<string>('auto');
  const [showQualityMenu, setShowQualityMenu] = useState(false);

  const speeds = [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2];
  const [currentSpeed, setCurrentSpeed] = useState<number>(1);
  const [showSpeedMenu, setShowSpeedMenu] = useState(false);

  const isDirectVideo = isDirectVideoFileUrl(videoUrl);
  const detected = isDirectVideo ? null : detectProvider(videoUrl);
  const directVideoSrc = isDirectVideo
    ? resolvePublicUploadUrl(videoUrl) || toEmbeddableVideoUrl(videoUrl)
    : null;
  const embedSrc = detected
    ? detected.provider === 'vimeo'
      ? buildVimeoPlayerEmbedUrl(detected.id)
      : buildYouTubeEmbedUrl(detected.id, window.location.origin)
    : isDirectVideo
      ? null
      : toEmbeddableVideoUrl(videoUrl);

  const postVimeo = useCallback((payload: Record<string, unknown>) => {
    iframeRef.current?.contentWindow?.postMessage(
      JSON.stringify(payload),
      'https://player.vimeo.com',
    );
  }, []);

  const postYouTube = useCallback((payload: Record<string, unknown>) => {
    iframeRef.current?.contentWindow?.postMessage(
      JSON.stringify(payload),
      'https://www.youtube.com',
    );
  }, []);

  const applySpeedToPlayer = useCallback(
    (speed: number) => {
      currentSpeedRef.current = speed;

      if (isDirectVideo) {
        const video = videoRef.current;
        if (video) video.playbackRate = speed;
        return;
      }

      if (!detected) return;

      if (detected.provider === 'vimeo') {
        postVimeo({ method: 'setPlaybackRate', value: speed });
      } else if (detected.provider === 'youtube') {
        postYouTube({ event: 'command', func: 'setPlaybackRate', args: [speed] });
      }
    },
    [detected, isDirectVideo, postVimeo, postYouTube],
  );

  /* ─── Fullscreen ─── */

  const toggleFullscreen = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    if (document.fullscreenElement) {
      document.exitFullscreen().catch(() => {});
    } else {
      el.requestFullscreen().catch(() => {});
    }
  }, []);

  /* ─── Play / Pause ─── */

  const togglePlayPause = useCallback(() => {
    if (isDirectVideo) {
      const video = videoRef.current;
      if (!video) return;
      if (video.paused) {
        void video.play();
      } else {
        video.pause();
      }
      return;
    }

    const iframe = iframeRef.current;
    if (!iframe?.contentWindow || !detected) return;

    if (detected.provider === 'vimeo') {
      postVimeo({ method: isPlaying ? 'pause' : 'play' });
    } else if (detected.provider === 'youtube') {
      postYouTube({ event: 'command', func: isPlaying ? 'pauseVideo' : 'playVideo', args: [] });
    }
  }, [isPlaying, detected, isDirectVideo, postVimeo, postYouTube]);

  /* ─── Mute / Unmute ─── */

  const toggleMute = useCallback(() => {
    const newMutedState = !isMuted;

    if (isDirectVideo) {
      const video = videoRef.current;
      if (video) video.muted = newMutedState;
      setIsMuted(newMutedState);
      return;
    }

    const iframe = iframeRef.current;
    if (!iframe?.contentWindow || !detected) return;

    if (detected.provider === 'vimeo') {
      postVimeo({ method: 'setVolume', value: newMutedState ? 0 : 1 });
    } else if (detected.provider === 'youtube') {
      postYouTube({ event: 'command', func: newMutedState ? 'mute' : 'unMute', args: [] });
    }

    setIsMuted(newMutedState);
  }, [isMuted, detected, isDirectVideo, postVimeo, postYouTube]);

  /* ─── Seek ─── */

  const seekTo = useCallback(
    (seconds: number) => {
      const clamped = Math.max(0, Math.min(seconds, duration || Infinity));

      if (isDirectVideo) {
        const video = videoRef.current;
        if (video) video.currentTime = clamped;
        setCurrentTime(clamped);
        return;
      }

      const iframe = iframeRef.current;
      if (!iframe?.contentWindow || !detected) return;

      if (detected.provider === 'vimeo') {
        postVimeo({ method: 'setCurrentTime', value: clamped });
      } else if (detected.provider === 'youtube') {
        postYouTube({ event: 'command', func: 'seekTo', args: [clamped, true] });
      }

      setCurrentTime(clamped);
    },
    [detected, duration, isDirectVideo, postVimeo, postYouTube],
  );

  /* ─── Quality ─── */

  const setQuality = useCallback(
    (qualityId: string) => {
      const iframe = iframeRef.current;
      if (!iframe?.contentWindow || !detected) return;

      if (detected.provider === 'vimeo') {
        iframe.contentWindow.postMessage(
          JSON.stringify({ method: 'setQuality', value: qualityId }),
          'https://player.vimeo.com',
        );
      } else if (detected.provider === 'youtube') {
        iframe.contentWindow.postMessage(
          JSON.stringify({ event: 'command', func: 'setPlaybackQuality', args: [qualityId] }),
          'https://www.youtube.com',
        );
      }

      setCurrentQuality(qualityId);
      setShowQualityMenu(false);
    },
    [detected],
  );

  /* ─── Speed ─── */

  const setSpeed = useCallback(
    (speed: number) => {
      applySpeedToPlayer(speed);
      setCurrentSpeed(speed);
      setShowSpeedMenu(false);
    },
    [applySpeedToPlayer],
  );

  /* ─── Seek bar drag ─── */

  const calcSeekFromMouse = useCallback(
    (clientX: number) => {
      const bar = seekBarRef.current;
      if (!bar || !duration) return;
      const rect = bar.getBoundingClientRect();
      const pct = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      seekTo(pct * duration);
    },
    [duration, seekTo],
  );

  const handleSeekMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      e.preventDefault();
      setIsSeeking(true);
      calcSeekFromMouse(e.clientX);

      const onMove = (ev: MouseEvent) => calcSeekFromMouse(ev.clientX);
      const onUp = () => {
        setIsSeeking(false);
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
      };
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
    },
    [calcSeekFromMouse],
  );

  /* ─── PostMessage listener: play/pause state + time updates ─── */

  useEffect(() => {
    const iframe = iframeRef.current;

    const handleMessage = (e: MessageEvent) => {
      /* ---------- Vimeo ---------- */
      if (e.origin === 'https://player.vimeo.com') {
        let data: Record<string, unknown>;
        try {
          data = typeof e.data === 'string' ? JSON.parse(e.data) : e.data;
        } catch {
          return;
        }

        // When Vimeo is ready, subscribe to events
        if (data.event === 'ready' && iframe?.contentWindow) {
          playerReadyRef.current = true;
          ['play', 'pause', 'timeupdate', 'qualitychange', 'playbackratechange', 'volumechange'].forEach((evt) => {
            iframe.contentWindow?.postMessage(
              JSON.stringify({ method: 'addEventListener', value: evt }),
              'https://player.vimeo.com',
            );
          });
          // Request duration and qualities
          iframe.contentWindow?.postMessage(
            JSON.stringify({ method: 'getDuration' }),
            'https://player.vimeo.com',
          );
          iframe.contentWindow?.postMessage(
            JSON.stringify({ method: 'getQualities' }),
            'https://player.vimeo.com',
          );
          if (currentSpeedRef.current !== 1) {
            iframe.contentWindow.postMessage(
              JSON.stringify({ method: 'setPlaybackRate', value: currentSpeedRef.current }),
              'https://player.vimeo.com',
            );
          }
        }

        if (data.event === 'timeupdate') {
          const td = data.data as Record<string, number> | undefined;
          if (td) {
            if (!isSeeking) setCurrentTime(td.seconds ?? 0);
            if (td.duration) setDuration(td.duration);
          }
        }

        if (data.method === 'getDuration') {
          setDuration((data.value as number) || 0);
        }

        if (data.method === 'getQualities' && Array.isArray(data.value)) {
          const vimeoQualities = data.value as { id: string; label: string; active?: boolean }[];
          setQualities(vimeoQualities);
          const active = vimeoQualities.find((q) => q.active);
          if (active) setCurrentQuality(active.id);
        }

        if (data.event === 'qualitychange') {
          const qd = data.data as { quality?: string } | undefined;
          if (qd?.quality) setCurrentQuality(qd.quality);
        }

        if (data.event === 'playbackratechange') {
          const rd = data.data as { playbackRate?: number } | undefined;
          if (rd?.playbackRate) setCurrentSpeed(rd.playbackRate);
        }

        if (data.event === 'volumechange') {
          const vd = data.data as { volume?: number } | undefined;
          if (typeof vd?.volume === 'number') setIsMuted(vd.volume === 0);
        }

        if (data.event === 'play') setIsPlaying(true);
        if (data.event === 'pause') setIsPlaying(false);
      }

      /* ---------- YouTube ---------- */
      if (e.origin === 'https://www.youtube.com') {
        let data: Record<string, unknown>;
        try {
          data = typeof e.data === 'string' ? JSON.parse(e.data) : e.data;
        } catch {
          return;
        }

        if (data.event === 'onReady') {
          playerReadyRef.current = true;
          iframe?.contentWindow?.postMessage(
            JSON.stringify({ event: 'listening', id: iframe?.id || '' }),
            'https://www.youtube.com',
          );
          if (currentSpeedRef.current !== 1) {
            iframe?.contentWindow?.postMessage(
              JSON.stringify({
                event: 'command',
                func: 'setPlaybackRate',
                args: [currentSpeedRef.current],
              }),
              'https://www.youtube.com',
            );
          }
        }

        // YouTube periodically sends infoDelivery with playerState, currentTime, duration
        if (data.event === 'infoDelivery') {
          const info = data.info as Record<string, any> | undefined;
          if (info) {
            if (typeof info.currentTime === 'number' && !isSeeking) {
              setCurrentTime(info.currentTime);
            }
            if (typeof info.duration === 'number' && info.duration > 0) {
              setDuration(info.duration);
            }
            if (typeof info.playerState === 'number') {
              setIsPlaying(info.playerState === 1);
            }
            if (info.availableQualityLevels && Array.isArray(info.availableQualityLevels)) {
              setQualities(
                info.availableQualityLevels.map((q: string) => ({ id: q, label: q === 'highres' ? 'High Res' : q === 'hd1080' ? '1080p' : q === 'hd720' ? '720p' : q === 'large' ? '480p' : q === 'medium' ? '360p' : q === 'small' ? '240p' : q === 'tiny' ? '144p' : q === 'auto' ? 'Auto' : q }))
              );
            }
            if (info.playbackQuality) {
              setCurrentQuality(info.playbackQuality);
            }
            if (info.playbackRate) {
              setCurrentSpeed(info.playbackRate);
            }
            if (typeof info.muted === 'boolean') {
              setIsMuted(info.muted);
            }
          }
        }

        if (data.event === 'onStateChange') {
          setIsPlaying(data.info === 1);
        }
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isSeeking]);

  /* ─── YouTube: start listening for player events on iframe load ─── */

  useEffect(() => {
    playerReadyRef.current = false;
  }, [embedSrc, directVideoSrc]);

  useEffect(() => {
    currentSpeedRef.current = currentSpeed;
  }, [currentSpeed]);

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe || detected?.provider !== 'youtube') return;

    const onLoad = () => {
      iframe.contentWindow?.postMessage(
        JSON.stringify({ event: 'listening', id: iframe.id || '' }),
        'https://www.youtube.com',
      );
    };

    iframe.addEventListener('load', onLoad);
    return () => iframe.removeEventListener('load', onLoad);
  }, [embedSrc, detected]);

  /* ─── HTML5 video: sync state from native element ─── */

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !isDirectVideo) return;

    const onLoadedMetadata = () => {
      setDuration(video.duration || 0);
      video.playbackRate = currentSpeedRef.current;
    };
    const onTimeUpdate = () => {
      if (!isSeeking) setCurrentTime(video.currentTime);
    };
    const onPlay = () => setIsPlaying(true);
    const onPause = () => setIsPlaying(false);
    const onVolumeChange = () => setIsMuted(video.muted || video.volume === 0);

    video.addEventListener('loadedmetadata', onLoadedMetadata);
    video.addEventListener('timeupdate', onTimeUpdate);
    video.addEventListener('play', onPlay);
    video.addEventListener('pause', onPause);
    video.addEventListener('volumechange', onVolumeChange);

    return () => {
      video.removeEventListener('loadedmetadata', onLoadedMetadata);
      video.removeEventListener('timeupdate', onTimeUpdate);
      video.removeEventListener('play', onPlay);
      video.removeEventListener('pause', onPause);
      video.removeEventListener('volumechange', onVolumeChange);
    };
  }, [directVideoSrc, isDirectVideo, isSeeking]);

  /* ─── Fullscreen interception + keyboard shortcuts ─── */

  useEffect(() => {
    const handleFullscreenChange = () => {
      const fsEl = document.fullscreenElement;
      const iframe = iframeRef.current;
      const container = containerRef.current;
      setIsFullscreen(!!fsEl);

      if (fsEl && fsEl === iframe && container) {
        document.exitFullscreen()
          .then(() => container.requestFullscreen())
          .catch(() => {});
      }
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  /* ─── Keyboard: ← → seek, Space play/pause, F fullscreen ─── */

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

      switch (e.key) {
        case 'ArrowRight':
          e.preventDefault();
          seekTo(currentTime + 10);
          break;
        case 'ArrowLeft':
          e.preventDefault();
          seekTo(Math.max(0, currentTime - 10));
          break;
        case ' ':
        case 'k':
        case 'K':
          e.preventDefault();
          togglePlayPause();
          break;
        case 'f':
        case 'F':
          e.preventDefault();
          toggleFullscreen();
          break;
        case 'm':
        case 'M':
          e.preventDefault();
          toggleMute();
          break;
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [currentTime, seekTo, togglePlayPause, toggleFullscreen, toggleMute]);

  /* ─── No video fallback ─── */

  if (!embedSrc && !directVideoSrc) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[280px] text-chalk font-mono text-sm">
        No video link configured.
      </div>
    );
  }

  /* ─── Click handling: single = play/pause, double = fullscreen ─── */

  const handleOverlayClick = (e: React.MouseEvent) => {
    e.stopPropagation();

    if (showQualityMenu) {
      setShowQualityMenu(false);
      return;
    }
    if (showSpeedMenu) {
      setShowSpeedMenu(false);
      return;
    }

    if (clickTimer.current) {
      clearTimeout(clickTimer.current);
      clickTimer.current = null;
      toggleFullscreen();
      return;
    }

    clickTimer.current = setTimeout(() => {
      clickTimer.current = null;
      togglePlayPause();
    }, 300);
  };

  const progress = duration ? (currentTime / duration) * 100 : 0;

  return (
    <div
      ref={containerRef}
      className="relative w-full h-full min-h-[280px] bg-black aspect-video rounded overflow-hidden select-none group"
      onContextMenu={(e) => {
        e.preventDefault();
        e.stopPropagation();
      }}
    >
      {isDirectVideo ? (
        <video
          ref={videoRef}
          src={directVideoSrc ?? undefined}
          title={title}
          className="absolute inset-0 h-full w-full border-0 object-contain bg-black"
          playsInline
          preload="metadata"
        />
      ) : (
        <iframe
          ref={iframeRef}
          src={embedSrc ?? undefined}
          title={title}
          className="absolute inset-0 h-full w-full border-0"
          allow="autoplay; fullscreen; picture-in-picture; encrypted-media"
        />
      )}

      {/* Full-area overlay — blocks ALL right-clicks, never toggled */}
      <div
        className="absolute inset-0 z-10 cursor-pointer"
        onContextMenu={(e) => {
          e.preventDefault();
          e.stopPropagation();
        }}
        onMouseDown={(e) => {
          if (e.button !== 0) {
            e.preventDefault();
            e.stopPropagation();
          }
        }}
        onClick={handleOverlayClick}
        onDragStart={(e) => e.preventDefault()}
      />

      {/* ─── Custom controls bar ─── */}
      <div
        className="
          absolute bottom-0 left-0 right-0 z-20
          bg-gradient-to-t from-black/80 via-black/40 to-transparent
          pt-10 pb-2 px-3
          opacity-0 group-hover:opacity-100
          transition-opacity duration-300 ease-in-out
        "
        onContextMenu={(e) => {
          e.preventDefault();
          e.stopPropagation();
        }}
      >
        {/* Seek bar */}
        <div
          ref={seekBarRef}
          className="
            w-full h-[5px] bg-white/20 rounded-full cursor-pointer mb-2
            hover:h-[7px] transition-all duration-150
            relative group/seek
          "
          onMouseDown={handleSeekMouseDown}
          onContextMenu={(e) => {
            e.preventDefault();
            e.stopPropagation();
          }}
        >
          {/* Progress fill */}
          <div
            className="h-full bg-cyan-400 rounded-full relative"
            style={{ width: `${progress}%` }}
          >
            {/* Seek handle */}
            <div
              className="
                absolute right-0 top-1/2 -translate-y-1/2
                w-3.5 h-3.5 bg-white rounded-full shadow-md
                opacity-0 group-hover/seek:opacity-100
                transition-opacity duration-150
              "
            />
          </div>
        </div>

        {/* Bottom row: play/pause + time on left, fullscreen on right */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {/* Play/Pause */}
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                togglePlayPause();
              }}
              onContextMenu={(e) => {
                e.preventDefault();
                e.stopPropagation();
              }}
              className="
                flex items-center justify-center w-7 h-7
                text-white/90 hover:text-white
                transition-colors cursor-pointer
              "
              title={isPlaying ? 'Pause' : 'Play'}
              aria-label={isPlaying ? 'Pause' : 'Play'}
            >
              {isPlaying ? <Pause size={16} /> : <Play size={16} />}
            </button>

            {/* Skip backward 10s */}
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                seekTo(Math.max(0, currentTime - 10));
              }}
              onContextMenu={(e) => {
                e.preventDefault();
                e.stopPropagation();
              }}
              className="
                flex items-center justify-center w-7 h-7
                text-white/70 hover:text-white text-[10px] font-bold
                transition-colors cursor-pointer
              "
              title="Back 10s (←)"
              aria-label="Seek backward 10 seconds"
            >
              -10
            </button>

            {/* Skip forward 10s */}
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                seekTo(currentTime + 10);
              }}
              onContextMenu={(e) => {
                e.preventDefault();
                e.stopPropagation();
              }}
              className="
                flex items-center justify-center w-7 h-7
                text-white/70 hover:text-white text-[10px] font-bold
                transition-colors cursor-pointer
              "
              title="Forward 10s (→)"
              aria-label="Seek forward 10 seconds"
            >
              +10
            </button>

            {/* Mute/Unmute */}
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                toggleMute();
              }}
              onContextMenu={(e) => {
                e.preventDefault();
                e.stopPropagation();
              }}
              className="
                flex items-center justify-center w-7 h-7 ml-1
                text-white/80 hover:text-white
                transition-colors cursor-pointer
              "
              title={isMuted ? 'Unmute (M)' : 'Mute (M)'}
              aria-label={isMuted ? 'Unmute' : 'Mute'}
            >
              {isMuted ? <VolumeX size={16} /> : <Volume2 size={16} />}
            </button>

            {/* Time display */}
            <span className="text-[11px] font-mono text-white/60 ml-1">
              {formatTime(currentTime)} / {formatTime(duration)}
            </span>
          </div>

          {/* Right side: Speed, Quality & Fullscreen */}
          <div className="flex items-center gap-1">
            {/* Speed Menu */}
            <div className="relative flex items-center">
              {showSpeedMenu && (
                <div
                  className="absolute bottom-full right-0 mb-2 w-20 bg-black/95 border border-white/10 rounded-md py-1 z-30"
                  onContextMenu={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                  }}
                >
                  {speeds.map((s) => (
                    <button
                      key={s}
                      type="button"
                      className={`block w-full text-left px-3 py-1.5 text-xs hover:bg-white/20 transition-colors ${
                        currentSpeed === s ? 'text-cyan-400 font-bold' : 'text-white/80'
                      }`}
                      onClick={(e) => {
                        e.stopPropagation();
                        setSpeed(s);
                      }}
                    >
                      {s}x
                    </button>
                  ))}
                </div>
              )}
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setShowQualityMenu(false);
                  setShowSpeedMenu((prev) => !prev);
                }}
                onContextMenu={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                }}
                className="
                  flex items-center justify-center h-7 px-2 mr-1
                  text-white/80 hover:text-white text-xs font-bold font-mono
                  transition-colors cursor-pointer
                "
                title="Playback Speed"
                aria-label="Playback Speed"
              >
                {currentSpeed}x
              </button>
            </div>

            {/* Quality Menu */}
            {qualities.length > 0 && (
              <div className="relative flex items-center">
                {showQualityMenu && (
                  <div
                    className="absolute bottom-full right-0 mb-2 w-28 bg-black/95 border border-white/10 rounded-md py-1 z-30"
                    onContextMenu={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                    }}
                  >
                    {qualities.map((q) => (
                      <button
                        key={q.id}
                        type="button"
                        className={`block w-full text-left px-3 py-1.5 text-xs hover:bg-white/20 transition-colors ${
                          currentQuality === q.id ? 'text-cyan-400 font-bold' : 'text-white/80'
                        }`}
                        onClick={(e) => {
                          e.stopPropagation();
                          setQuality(q.id);
                        }}
                      >
                        {q.label}
                      </button>
                    ))}
                  </div>
                )}
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setShowSpeedMenu(false);
                    setShowQualityMenu((prev) => !prev);
                  }}
                  onContextMenu={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                  }}
                  className="
                    flex items-center justify-center w-7 h-7
                    text-white/80 hover:text-white
                    transition-colors cursor-pointer
                  "
                  title="Quality Settings"
                  aria-label="Quality Settings"
                >
                  <Settings size={16} />
                </button>
              </div>
            )}

            {/* Fullscreen */}
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                toggleFullscreen();
              }}
              onContextMenu={(e) => {
                e.preventDefault();
                e.stopPropagation();
              }}
              className="
                flex items-center justify-center w-7 h-7
                text-white/80 hover:text-white
                transition-colors cursor-pointer
              "
              title={isFullscreen ? 'Exit Fullscreen (F)' : 'Fullscreen (F)'}
              aria-label={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
            >
              {isFullscreen ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
