import assert from 'node:assert/strict';
import {within24Hours} from '../lib/reading.ts';

const now=Date.parse('2026-09-13T12:00:00Z');
const post={publishedAt:'2026-09-12T00:00:00Z',firstPublishedAt:'2026-09-12T13:00:00Z'};
assert.equal(within24Hours(post,now),true); // Source is 36h old; on our site for 23h.
assert.equal(within24Hours(post,now+3600_000),false);
assert.equal(within24Hours({...post,commentsFetchedAt:'2026-09-13T11:59:00Z'},now+3600_000),false);
assert.equal(within24Hours({...post,firstPublishedAt:'2026-09-13T13:00:00Z'},now),false);
assert.equal(within24Hours({...post,firstPublishedAt:'invalid'},now),false);
assert.equal(within24Hours({publishedAt:post.publishedAt,commentsFetchedAt:'2026-09-12T13:00:00Z'},now),true);
console.log('First publication retention: old sources, expiry boundary, immutable lifetime and legacy fallback passed.');
