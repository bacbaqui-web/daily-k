type MarkerPost = {
  excerpt?: string;
  content?: { type: string; text?: string }[];
  comments?: { text: string }[];
  portalLinks?: string[];
};
export function contentMarkers(post: MarkerPost): { label: string; url: string }[] {
  const texts = [
    ...(post.comments || []).map(c => c.text),
    ...(post.portalLinks || []),
    ...(post.content || []).filter(b => b.type === 'text').map(b => b.text || ''),
    post.excerpt || '',
  ];
  const links: { label: string; url: string }[] = [];
  const seen = new Set<string>();
  const pattern = /(?:^|[^\w@.-])((?:https?:\/\/)?(?:[a-z0-9-]+\.)*(?:instagram|x|twitter)\.com(?:[\/?#][^\s<>"'`]*)?)(?=$|[^\w.-])/gi;
  for (const text of texts) for (const match of text.matchAll(pattern)) {
    const raw = match[1].replace(/[.,;!\)\]\}]+$/, '');
    try {
      const url = new URL(/^https?:\/\//i.test(raw) ? raw : `https://${raw}`);
      const host = url.hostname.toLowerCase();
      if (url.username || url.password || !['https:', 'http:'].includes(url.protocol)) continue;
      const instagram = host === 'instagram.com' || host.endsWith('.instagram.com');
      const x = ['x.com', 'twitter.com'].some(domain => host === domain || host.endsWith(`.${domain}`));
      if ((!instagram && !x) || seen.has(url.href)) continue;
      seen.add(url.href);
      links.push({ label: instagram ? '인스타' : 'X', url: url.href });
    } catch { /* Ignore malformed addresses. */ }
  }
  return links;
}
