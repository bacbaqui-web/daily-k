import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {isGitHubBrief, isGitHubIndex, validGitHubDate} from '../lib/github.ts';
const root = new URL('../public/data/github/', import.meta.url);
const index = JSON.parse(readFileSync(new URL('index.json', root), 'utf8'));
assert.ok(isGitHubIndex(index));
assert.ok(!validGitHubDate('2026-02-30'));
assert.ok(!isGitHubIndex({schemaVersion: 1, editions: [{date: '2026-11-17', path: '../../secret', count: 10}]}));
for (const entry of index.editions) {
  const raw = readFileSync(new URL(entry.path, root), 'utf8');
  assert.equal(raw, readFileSync(new URL(`../docs/data/github/${entry.path}`, import.meta.url), 'utf8'));
  const brief = JSON.parse(raw);
  assert.ok(isGitHubBrief(brief, entry.count), entry.date);
  const malformed: any = structuredClone(brief); malformed.items[0] = null;
  assert.ok(!isGitHubBrief(malformed), 'Malformed items fail without crashing');
  const reordered = structuredClone(brief); [reordered.items[0], reordered.items[1]] = [reordered.items[1], reordered.items[0]];
  assert.ok(!isGitHubBrief(reordered), 'Never silently accept reordered rankings');
  const unsafe = structuredClone(brief); unsafe.items[0].sources[0].url = 'javascript:alert(1)';
  assert.ok(!isGitHubBrief(unsafe));
  const invalidEmphasis = structuredClone(brief); invalidEmphasis.items[0].emphasis = ['본문에 없는 강조 문구'];
  assert.ok(!isGitHubBrief(invalidEmphasis), 'Emphasis must refer to existing copy');
  const truncated = structuredClone(brief); truncated.items.pop();
  assert.ok(!isGitHubBrief(truncated), 'Never publish only part of the captured ranking');
  const traversal = structuredClone(brief); traversal.items[0].image.src = '/daily-k/data/github/images/../../private.png';
  assert.ok(!isGitHubBrief(traversal));
  for (const item of brief.items) {
    const path = item.image.src.replace('/daily-k/', '');
    const a = readFileSync(new URL(`../public/${path}`, import.meta.url));
    const b = readFileSync(new URL(`../docs/${path}`, import.meta.url));
    assert.ok(a.length > 100); assert.deepEqual(a, b);
  }
}
console.log(`GitHub: ${index.editions.length} edition(s), full ranking, safe links and image parity verified`);

const sample = JSON.parse(readFileSync(new URL(index.editions[0].path, root), 'utf8'));
const variable = {...sample, itemCount: 7, items: sample.items.slice(0, 7).map((item: object) => ({...item, starsTotal: 1234, forks: 56, language: null}))};
assert.ok(isGitHubBrief(variable, 7), 'Any complete count and unspecified language are valid');
assert.equal(isGitHubBrief(variable, 10), false, 'Index and edition counts must agree');
assert.ok(isGitHubIndex({schemaVersion: 1, editions: [{date: sample.date, path: `${sample.date}.json`, count: 7}]}));
delete variable.items[0].forks;
assert.equal(isGitHubBrief(variable), false, 'New editions require all captured metrics');
variable.items[0].forks = -1;
assert.equal(isGitHubBrief(variable), false, 'Negative metrics are invalid');
