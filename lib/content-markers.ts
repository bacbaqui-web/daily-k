type MarkerPost = {
  excerpt?: string;
  content?: { type: string; text?: string }[];
  comments?: { text: string }[];
  portalLinks?: string[];
};
export function contentMarkers(post: MarkerPost): string[] {
  const text = [post.excerpt || '', ...(post.content || []).filter(b => b.type === 'text').map(b => b.text || ''), ...(post.comments || []).map(c => c.text), ...(post.portalLinks || [])].join('\n');
  return [
    { label: '인스타', pattern: /(?:^|[^\w@.-])(?:https?:\/\/)?(?:[a-z0-9-]+\.)*instagram\.com(?:[\/?#\s]|$)/i },
    { label: 'X', pattern: /(?:^|[^\w@.-])(?:https?:\/\/)?(?:[a-z0-9-]+\.)*(?:x|twitter)\.com(?:[\/?#\s]|$)/i },
    { label: 'leaked', pattern: /\bleaked\b/i },
  ].filter(marker => marker.pattern.test(text)).map(marker => marker.label);
}
