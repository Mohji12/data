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

/** Minimal chrome + no keyboard shortcuts; playback controlled via postMessage overlay. */
export function buildVimeoPlayerEmbedUrl(videoId: string): string {
  const params = new URLSearchParams({
    title: '0',
    byline: '0',
    portrait: '0',
    keyboard: '1',
    controls: '1',
    dnt: '1',
  });
  return `https://player.vimeo.com/video/${videoId}?${params.toString()}`;
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
    controls: '1',
    disablekb: '0',
  });
  return `https://www.youtube.com/embed/${videoId}?${params.toString()}`;
}
