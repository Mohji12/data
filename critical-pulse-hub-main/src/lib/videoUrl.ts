/**
 * Normalize stored video links (Vimeo, YouTube, etc.) for use in <iframe src="...">.
 * Legacy DB values are often full player URLs, e.g. https://player.vimeo.com/video/531669636
 */
export function toEmbeddableVideoUrl(rawUrl?: string | null): string {
  const url = String(rawUrl || '').trim();
  if (!url) return '';

  try {
    const u = new URL(url);
    const host = u.hostname.toLowerCase();

    if (host === 'player.vimeo.com' && u.pathname.startsWith('/video/')) {
      return u.toString();
    }

    if (host.endsWith('vimeo.com')) {
      const parts = u.pathname.split('/').filter(Boolean);
      if (parts[0] === 'video' && parts[1]) {
        return `https://player.vimeo.com/video/${parts[1]}`;
      }
      if (parts[0] && /^\d+$/.test(parts[0])) {
        return `https://player.vimeo.com/video/${parts[0]}`;
      }
    }

    if (host.includes('youtube.com') && u.pathname.startsWith('/embed/')) {
      return u.toString();
    }

    if (host.includes('youtube.com') && u.pathname === '/watch') {
      const id = u.searchParams.get('v');
      if (id) return `https://www.youtube.com/embed/${id}`;
    }

    if (host.includes('youtu.be')) {
      const id = u.pathname.replace(/^\/+/, '').split('/')[0];
      if (id) return `https://www.youtube.com/embed/${id}`;
    }

    if (host.includes('youtube.com')) {
      const parts = u.pathname.split('/').filter(Boolean);
      if (parts.length >= 2 && (parts[0] === 'shorts' || parts[0] === 'live')) {
        return `https://www.youtube.com/embed/${parts[1]}`;
      }
    }
  } catch {
    // fall through to legacy string replacements
  }

  return url
    .replace('watch?v=', 'embed/')
    .replace('youtu.be/', 'youtube.com/embed/');
}

export function parseVimeoVideoId(rawUrl?: string | null): string | null {
  const embed = toEmbeddableVideoUrl(rawUrl);
  if (!embed) return null;
  try {
    const u = new URL(embed);
    if (u.hostname === 'player.vimeo.com') {
      const match = u.pathname.match(/\/video\/(\d+)/);
      return match?.[1] ?? null;
    }
  } catch {
    return null;
  }
  return null;
}

/** Minimal chrome; native controls hidden — custom overlay provides all UI. */
export function buildVimeoPlayerEmbedUrl(videoId: string, playerId?: string): string {
  const params = new URLSearchParams({
    api: '1',           // required for postMessage timeupdate / getCurrentTime
    title: '0',
    byline: '0',
    portrait: '0',
    keyboard: '0',      // disable Vimeo keyboard (our overlay handles shortcuts)
    controls: '0',      // hide native controls (custom controls on overlay)
    dnt: '1',
    transcript: '0',
    pip: '0',
    allowfullscreen: '1',
    // speed=1 enables the playback-rate API (required for setPlaybackRate postMessage).
    speed: '1',
  });
  if (playerId) params.set('player_id', playerId);
  return `https://player.vimeo.com/video/${videoId}?${params.toString()}`;
}

/** Direct file URLs (MP4 etc.) — use HTML5 <video>, not iframe postMessage. */
export function isDirectVideoFileUrl(rawUrl?: string | null): boolean {
  const url = String(rawUrl || '').trim();
  if (!url) return false;
  if (parseVimeoVideoId(url) || parseYouTubeVideoId(url)) return false;

  try {
    const u = new URL(url, 'https://placeholder.local');
    const path = u.pathname.toLowerCase();
    return (
      /\.(mp4|webm|ogg|mov|m4v)(\?|$)/i.test(path) ||
      path.includes('/upload/batch_videos/') ||
      path.includes('/upload/videos/')
    );
  } catch {
    return /\.(mp4|webm|ogg|mov|m4v)(\?|$)/i.test(url.toLowerCase());
  }
}

export function parseYouTubeVideoId(rawUrl?: string | null): string | null {
  const embed = toEmbeddableVideoUrl(rawUrl);
  if (!embed) return null;
  try {
    const u = new URL(embed);
    const host = u.hostname.toLowerCase();
    if (host.includes('youtube.com') && u.pathname.startsWith('/embed/')) {
      return u.pathname.split('/')[2] || null;
    }
    if (host.includes('youtu.be')) {
      return u.pathname.replace(/^\/+/, '').split('/')[0] || null;
    }
  } catch {
    return null;
  }
  return null;
}

export function buildYouTubeEmbedUrl(videoId: string, origin: string): string {
  const params = new URLSearchParams({
    enablejsapi: '1',
    origin,
    rel: '0',
    modestbranding: '1',
    controls: '0',      // custom overlay controls; we poll getCurrentTime via JS API
    disablekb: '1',     // keyboard handled by overlay
  });
  return `https://www.youtube.com/embed/${videoId}?${params.toString()}`;
}
