export type GitHubItem = {
  rank: number; repo: string; url: string; starsToday: number;
  title: string; summary: string; explanation: string[]; useCase: string;
  requirements: string; sources: {label: string; url: string}[];
  image: {src: string; alt: string; sourceUrl: string; caption: string};
};
export type GitHubBrief = {
  schemaVersion: 1; date: string; capturedAt: string; publishedAt: string;
  rankingUrl: string; intro: string; items: GitHubItem[];
};
export type GitHubIndex = {schemaVersion: 1; editions: {date: string; path: string; count: number}[]};
export const validGitHubDate = (v: unknown): v is string => typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v) && !Number.isNaN(Date.parse(`${v}T00:00:00Z`)) && new Date(`${v}T00:00:00Z`).toISOString().slice(0, 10) === v;
const text = (v: unknown): v is string => typeof v === 'string' && !!v.trim();
const url = (v: unknown): v is string => text(v) && /^https:\/\//.test(v);
const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object';
export function isGitHubIndex(v: unknown): v is GitHubIndex {
  return object(v) && v.schemaVersion === 1 && Array.isArray(v.editions) && v.editions.every(e => object(e) && validGitHubDate(e.date) && e.path === `${e.date}.json` && e.count === 10) && new Set(v.editions.map(e => e.date)).size === v.editions.length;
}
export function isGitHubBrief(v: unknown): v is GitHubBrief {
  if (!object(v) || v.schemaVersion !== 1 || !validGitHubDate(v.date) || !text(v.intro) || v.rankingUrl !== 'https://github.com/trending?since=daily' || ![v.capturedAt, v.publishedAt].every(t => text(t) && !Number.isNaN(Date.parse(t))) || !Array.isArray(v.items) || v.items.length !== 10) return false;
  return v.items.every(object) && new Set(v.items.map(i => i.repo)).size === 10 && v.items.every((i, n) => object(i) && i.rank === n + 1 && text(i.repo) && /^[\w.-]+\/[\w.-]+$/.test(i.repo) && i.url === `https://github.com/${i.repo}` && Number.isInteger(i.starsToday) && Number(i.starsToday) >= 0 && [i.title, i.summary, i.useCase, i.requirements].every(text) && Array.isArray(i.explanation) && i.explanation.length > 0 && i.explanation.every(text) && Array.isArray(i.sources) && i.sources.length > 0 && i.sources.every(s => object(s) && text(s.label) && url(s.url)) && object(i.image) && text(i.image.src) && /^\/daily-k\/data\/github\/images\/[\w./-]+\.(png|jpg|webp)$/.test(i.image.src) && !i.image.src.includes('..') && text(i.image.alt) && text(i.image.caption) && url(i.image.sourceUrl));
}
