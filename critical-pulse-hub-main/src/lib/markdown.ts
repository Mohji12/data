/** True when the string looks like stored HTML (TipTap / rich editor output). */
export function looksLikeHtml(source: string): boolean {
  return /<[a-z][\s\S]*>/i.test(String(source || '').trim());
}

/**
 * Light sanitize for trusted admin HTML: strip script/style/iframe and on* handlers.
 * Not a full XSS library — descriptions are admin-authored.
 */
export function sanitizeBasicHtml(html: string): string {
  let out = String(html || '');
  out = out.replace(/<\s*(script|style|iframe|object|embed)\b[\s\S]*?<\/\s*\1\s*>/gi, '');
  out = out.replace(/<\s*(script|style|iframe|object|embed)\b[^>]*\/?\s*>/gi, '');
  out = out.replace(/\s+on[a-z]+\s*=\s*(['"]).*?\1/gi, '');
  out = out.replace(/\s+on[a-z]+\s*=\s*[^\s>]+/gi, '');
  out = out.replace(/\s(href|src)\s*=\s*(['"])\s*javascript:[\s\S]*?\2/gi, ' $1="#"');
  return out;
}

/** Render description: HTML from rich editor, or legacy Markdown. */
export function descriptionToSafeHtml(source: string): string {
  const text = String(source || '').trim();
  if (!text) return '';
  if (looksLikeHtml(text)) return sanitizeBasicHtml(text);
  return markdownToSafeHtml(text);
}

/**
 * Lightweight Markdown → safe HTML for course/batch descriptions.
 * Supports: headings (#–######), **bold**, *italic*, unordered lists, paragraphs.
 */
export function markdownToSafeHtml(source: string): string {
  const text = String(source || '').replace(/\r\n/g, '\n').trim();
  if (!text) return '';

  const escapeHtml = (s: string) =>
    s
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');

  const inline = (s: string) => {
    let out = escapeHtml(s);
    out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    out = out.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    return out;
  };

  const lines = text.split('\n');
  const html: string[] = [];
  let inList = false;
  let para: string[] = [];

  const flushPara = () => {
    if (!para.length) return;
    const body = para.map((l) => inline(l.trim())).join('<br />');
    html.push(`<p>${body}</p>`);
    para = [];
  };

  const closeList = () => {
    if (!inList) return;
    html.push('</ul>');
    inList = false;
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    const trimmed = line.trim();

    if (!trimmed) {
      flushPara();
      closeList();
      continue;
    }

    const heading = /^(#{1,6})\s+(.+)$/.exec(trimmed);
    if (heading) {
      flushPara();
      closeList();
      const level = Math.min(heading[1].length, 6);
      html.push(`<h${level}>${inline(heading[2])}</h${level}>`);
      continue;
    }

    const bullet = /^[-*•]\s+(.+)$/.exec(trimmed);
    if (bullet) {
      flushPara();
      if (!inList) {
        html.push('<ul>');
        inList = true;
      }
      html.push(`<li>${inline(bullet[1])}</li>`);
      continue;
    }

    closeList();
    para.push(trimmed);
  }

  flushPara();
  closeList();
  return html.join('');
}
