'use strict';
// Independent offline tests using Node's standard-library test runner and VM.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const { execFileSync } = require('node:child_process');
const source = fs.readFileSync(path.join(__dirname, '../src/browser-macro.js'), 'utf8');
const item = {id: '100', url: 'https://aagag.com/issue/?idx=100'};
const presence = {id:'100',url:item.url,title: '제목', body: true, all: true, allSelected: true, history: true, historyExpanded: true};
const preliminary = {expected: 1, comments: [{id: 'native-1', kCount: 11}]};
const data = {id: '100', url:item.url, observedAt: '2026-10-09T01:00:00.000Z', title: '제목', commentCounts: []};

function load(extra = {}) {
  const context = {URL, Date, ...extra};
  vm.runInNewContext(source, context, {filename: 'browser-macro.js'});
  return context;
}

function tabMock(overrides = {}) {
  const calls = {goto: [], reload: 0, evaluate: 0, snapshots: 0, clicks: [], waits: [], readiness: [], filters: []};
  let evaluations = 0;
  const tab = {
    url: async () => item.url,
    goto: async url => {calls.goto.push(url);},
    reload: async () => {calls.reload++;},
    playwright: {
      evaluate: async () => {calls.evaluate++; return [presence, preliminary, data][evaluations++ % 3];},
      domSnapshot: async () => {calls.snapshots++; return 'ordinary page';},
      locator: selector => ({click: async () => {calls.clicks.push(selector);}, first() { return this; }, filter(options) {calls.filters.push({selector, options}); return this;}, waitFor: async options => {calls.readiness.push({selector, options});}}),
      waitForTimeout: async ms => {calls.waits.push(ms);},
    },
  };
  Object.assign(tab, overrides);
  return {tab, calls};
}

function errorTab({snapshotError, reloadError, snapshot = 'ordinary page'} = {}) {
  const mock = tabMock();
  mock.tab.playwright.evaluate = async () => {mock.calls.evaluate++; throw new Error('transient evaluation error');};
  mock.tab.playwright.domSnapshot = async () => {
    mock.calls.snapshots++;
    if (snapshotError) throw new Error('snapshot unavailable');
    return snapshot;
  };
  mock.tab.reload = async () => {
    mock.calls.reload++;
    if (reloadError) throw new Error('reload unavailable');
  };
  return mock;
}

test('observed record is checkpointable and records one successful attempt', async () => {
  const macro = load();
  const {tab, calls} = tabMock();
  const result = await macro.collectPost(tab, item);
  assert.equal(result.status, 'observed');
  assert.equal(result.requestedId, '100');
  assert.equal(result.attempts.length, 1);
  assert.equal(calls.reload, 0);
});

test('navigates only when target differs and activates all comments/source history', async () => {
  const macro = load();
  const {tab, calls} = tabMock({url: async () => 'https://example.test/list'});
  let read = 0;
  tab.playwright.evaluate = async () => [{...presence, allSelected: false, historyExpanded: false}, preliminary, data][read++];
  const result = await macro.collectPost(tab, item);
  assert.equal(result.status, 'observed');
  assert.deepEqual(calls.goto, [item.url]);
  assert.deepEqual(calls.clicks, ['#comment_sort [sort=all]', '#history_bar']);
});

test('permanent evaluation errors are bounded at two attempts', async () => {
  const {tab, calls} = errorTab();
  const result = await load().collectPost(tab, item);
  assert.equal(result.status, 'failed');
  assert.equal(result.attempts.length, 2);
  assert.equal(calls.evaluate, 2);
  assert.match(result.error, /transient evaluation error/);
});

test('temporary failure recovers on the second attempt', async () => {
  const {tab, calls} = tabMock();
  let step = 0;
  tab.playwright.evaluate = async () => {
    calls.evaluate++;
    if (step++ === 0) throw new Error('temporary failure');
    return [presence, preliminary, data][step - 2];
  };
  const result = await load().collectPost(tab, item);
  assert.equal(result.status, 'observed');
  assert.equal(result.attempts.length, 2);
  assert.equal(calls.evaluate, 4);
});

test('bot denial stops without retrying or reloading', async () => {
  const {tab, calls} = errorTab({snapshot: 'Please verify you are human. CAPTCHA'});
  const result = await load().collectPost(tab, item);
  assert.equal(result.status, 'blocked');
  assert.equal(result.attempts.length, 1);
  assert.equal(calls.evaluate, 1);
  assert.equal(calls.reload, 0);
});

test('missing content returns a checkpointable blocked result', async () => {
  const {tab, calls} = tabMock();
  tab.playwright.evaluate = async () => {calls.evaluate++; return {title: null, body: false, error: 'missing'};};
  const result = await load().collectPost(tab, item);
  assert.equal(result.status, 'blocked_or_missing');
  assert.equal(result.attempts.length, 1);
  assert.equal(calls.evaluate, 1);
});

test('slice stops immediately after a blocked post and applies bounded politeness throttle', async () => {
  const {tab, calls} = tabMock();
  tab.playwright.evaluate = async () => {calls.evaluate++; return {title: null, body: false, error: 'missing'};};
  const result = await load().collectSlice(tab, [item, {...item, id: '101'}]);
  assert.equal(result.length, 1);
  assert.equal(result[0].status, 'blocked_or_missing');
  assert.deepEqual(calls.waits, [3000]);
});

test('failed snapshot in retry handling still returns a checkpointable failure', async () => {
  const {tab} = errorTab({snapshotError: true});
  const result = await load().collectPost(tab, item);
  assert.equal(result.status, 'failed');
  assert.ok(result.attempts.length <= 2);
});

test('failed reload in retry handling still returns a checkpointable failure', async () => {
  const {tab} = errorTab({reloadError: true});
  const result = await load().collectPost(tab, item);
  assert.equal(result.status, 'failed');
  assert.ok(result.attempts.length <= 2);
});

test('one retry performs at most one reload', async () => {
  const {tab, calls} = errorTab();
  await load().collectPost(tab, item);
  assert.equal(calls.reload, 1);
});

function parserTab({otherTitle = null, commentText = 'ㅋㅋㅋㅋㅋㅋㅋㅋㅋㅋㅋ', commentCountText = '1'} = {}) {
  const history = {getBoundingClientRect: () => ({height: 10})};
  const comment = {
    getAttribute: attr => attr === 'w_idx' ? 'native-7' : null,
    querySelector: selector => selector === '.content' ? {innerText: commentText} : {getAttribute: () => '2026-10-08 12:30:00'},
  };
  const elements = new Map([
    ['h1.title', {innerText: '제목'}],
    ['#vContent', {}],
    ['#comment_sort [sort=all]', {}],
    ['#comment_sort [sort=all].on', {}],
    ['#history_bar', {innerText: '총 0'}],
    ['#history_list', history],
    ['#header .odate', {textContent: '2026-10-08 12:00:00'}],
    ['#comment_cnt strong', {textContent: commentCountText}],
    ['h4.other', otherTitle === null ? null : {innerText: otherTitle}],
  ]);
  const document = {
    body: {innerText: 'normal content'},
    querySelector: selector => elements.get(selector) ?? null,
    querySelectorAll: selector => selector === '#comment .cmt[w_idx]' && commentText !== null ? [comment] : [],
  };
  const macro = load({document, location: {href: item.url}});
  const {tab, calls} = tabMock();
  tab.playwright.evaluate = async fn => {calls.evaluate++; return fn();};
  return {macro, tab, calls};
}

test('DOM extractor counts only native Hangul ㅋ characters', async () => {
  const {macro, tab} = parserTab({commentText: 'ㅋ ㅋㅋ kkk ㅎㅎ ㅋ'});
  const result = await macro.collectPost(tab, item);
  assert.equal(result.status, 'observed');
  assert.equal(result.commentCounts[0].id, 'native-7');
  assert.equal(result.commentCounts[0].kCount, 4);
});

test('DOM extractor tolerates absent optional source range heading', async () => {
  const {macro, tab} = parserTab();
  const result = await macro.collectPost(tab, item);
  assert.equal(result.status, 'observed');
  assert.equal(result.sourceRange, null);
});

test('DOM extractor tolerates present heading without an S: source range', async () => {
  const {macro, tab} = parserTab({otherTitle: '관련 글'});
  const result = await macro.collectPost(tab, item);
  assert.equal(result.status, 'observed');
  assert.equal(result.sourceRange, null);
});


test('ten-k preliminary count skips source expansion with explicit limited scope', async () => {
  const {tab, calls} = tabMock();
  let index = 0;
  tab.playwright.evaluate = async () => [
    {...presence, allSelected: false, historyExpanded: false},
    {expected: 1, comments: [{id: 'native-1', kCount: 10}]},
    {...data, commentCounts: [{id: 'native-1', kCount: 10}]},
  ][index++];
  const result = await load().collectPost(tab, item);
  assert.equal(result.status, 'observed');
  assert.equal(result.verificationScope, 'comments_only_below_threshold');
  assert.equal(result.mediaInspectionSkipped, true);
  assert.deepEqual(calls.clicks, ['#comment_sort [sort=all]']);
  assert.equal(calls.readiness.filter(entry => entry.selector === '#history_list .hsite').length, 0);
});

test('eleven-k preliminary count requires full source expansion', async () => {
  const {tab, calls} = tabMock();
  let index = 0;
  tab.playwright.evaluate = async () => [{...presence, historyExpanded: false}, preliminary, data][index++];
  const result = await load().collectPost(tab, item);
  assert.equal(result.verificationScope, 'full_candidate');
  assert.equal(result.mediaInspectionSkipped, false);
  assert.deepEqual(calls.clicks, ['#comment_sort [sort=all]', '#history_bar']);
  assert.equal(calls.readiness.filter(entry => entry.selector === '#history_list .hsite').length, 1);
});

test('preliminary threshold deduplicates repeated native comment IDs', async () => {
  const {tab, calls} = tabMock();
  let index = 0;
  tab.playwright.evaluate = async () => [
    {...presence, historyExpanded: false},
    {expected: 1, comments: [{id: 'native-1', kCount: 6}, {id: 'native-1', kCount: 6}]},
    data,
  ][index++];
  const result = await load().collectPost(tab, item);
  assert.equal(result.verificationScope, 'comments_only_below_threshold');
  assert.equal(calls.readiness.filter(entry => entry.selector === '#history_list .hsite').length, 0);
});


test('numeric count readiness requires visible digits before preliminary qualification', async () => {
  const {tab, calls} = tabMock();
  const evaluate = tab.playwright.evaluate;
  tab.playwright.evaluate = async fn => {
    if (calls.evaluate === 1) {
      const ready = calls.readiness.find(entry => entry.selector === '#comment_cnt strong');
      assert.ok(ready, 'numeric readiness must precede the preliminary read');
      assert.equal(ready.options.state, 'visible');
      assert.equal(ready.options.timeoutMs, 12000);
    }
    return evaluate(fn);
  };
  const result = await load().collectPost(tab, item);
  assert.equal(result.status, 'observed');
  const filter = calls.filters.find(entry => entry.selector === '#comment_cnt strong');
  assert.ok(filter);
  assert.equal(filter.options.hasText.test('0'), true);
  assert.equal(filter.options.hasText.test('11'), true);
  assert.equal(filter.options.hasText.test('...'), false);
  assert.equal(filter.options.hasText.test(''), false);
});

test('genuine zero native comments is a valid observed below-threshold record', async () => {
  const {macro, tab, calls} = parserTab({commentText: null, commentCountText: '0'});
  const result = await macro.collectPost(tab, item);
  assert.equal(result.status, 'observed');
  assert.equal(result.commentsExpected, 0);
  assert.equal(result.commentCounts.length, 0);
  assert.equal(result.verificationScope, 'comments_only_below_threshold');
  assert.equal(calls.readiness.filter(entry => entry.selector === '#history_list .hsite').length, 0);
});

test('loading placeholder cannot be mistaken for zero native comments', async () => {
  const {macro, tab, calls} = parserTab({commentText: null, commentCountText: '...'});
  const result = await macro.collectPost(tab, item);
  assert.equal(result.status, 'failed');
  assert.match(result.error, /Native comment count not ready or incomplete/);
  assert.equal(result.attempts.length, 2);
  assert.equal(calls.reload, 1);
  assert.equal(result.verificationScope, undefined);
});

test('serialized null count cannot be mistaken for a numeric zero', async () => {
  const {tab, calls} = tabMock();
  let index = 0;
  tab.playwright.evaluate = async () => {
    calls.evaluate++;
    return index++ % 2 ? {expected: null, comments: []} : presence;
  };
  const result = await load().collectPost(tab, item);
  assert.equal(result.status, 'failed');
  assert.match(result.error, /Native comment count not ready or incomplete/);
  assert.equal(result.attempts.length, 2);
  assert.equal(calls.evaluate, 4);
  assert.equal(calls.reload, 1);
});

test('native row-count mismatch fails after one bounded retry without source expansion', async () => {
  const {tab, calls} = tabMock();
  let index = 0;
  tab.playwright.evaluate = async () => {
    calls.evaluate++;
    return index++ % 2 ? {expected: 2, comments: [{id: 'native-1', kCount: 11}]} : {...presence, historyExpanded: false};
  };
  const result = await load().collectPost(tab, item);
  assert.equal(result.status, 'failed');
  assert.match(result.error, /1\/2/);
  assert.equal(result.attempts.length, 2);
  assert.equal(calls.evaluate, 4);
  assert.equal(calls.reload, 1);
  assert.equal(calls.clicks.includes('#history_bar'), false);
});

test('native row-count mismatch can recover on the second attempt', async () => {
  const {tab, calls} = tabMock();
  let index = 0;
  tab.playwright.evaluate = async () => {
    calls.evaluate++;
    return [presence, {expected: 2, comments: [{id: 'native-1', kCount: 11}]}, presence, preliminary, data][index++];
  };
  const result = await load().collectPost(tab, item);
  assert.equal(result.status, 'observed');
  assert.equal(result.attempts.length, 2);
  assert.equal(calls.reload, 1);
  assert.equal(result.verificationScope, 'full_candidate');
});

test('numeric readiness timeout is bounded and never reads provisional comments', async () => {
  const {tab, calls} = tabMock();
  tab.playwright.evaluate = async () => {calls.evaluate++; return presence;};
  tab.playwright.locator = selector => ({
    click: async () => {calls.clicks.push(selector);},
    filter() {return this;},
    waitFor: async () => {if(selector==='body')return;calls.readiness.push({selector}); throw new Error('numeric count readiness timeout');},
  });
  const result = await load().collectPost(tab, item);
  assert.equal(result.status, 'failed');
  assert.match(result.error, /numeric count readiness timeout/);
  assert.equal(result.attempts.length, 2);
  assert.equal(calls.evaluate, 2);
  assert.equal(calls.readiness.length, 2);
  assert.equal(calls.reload, 1);
});


test('already-selected all-comments control is still clicked before lazy-loading readiness', async () => {
  const {tab, calls} = tabMock();
  const evaluate = tab.playwright.evaluate;
  tab.playwright.evaluate = async fn => {
    if (calls.evaluate === 1) {
      assert.deepEqual(calls.clicks, ['#comment_sort [sort=all]']);
      assert.ok(calls.readiness.find(entry => entry.selector === '#comment_cnt strong'));
    }
    return evaluate(fn);
  };
  const result = await load().collectPost(tab, item);
  assert.equal(result.status, 'observed');
  assert.equal(result.attempts.length, 1);
  assert.deepEqual(calls.clicks, ['#comment_sort [sort=all]']);
  assert.equal(calls.reload, 0);
});

test('marked observed listing titles are excluded before any browser access', async () => {
  for (const marker of ['ㅇㅎ', 'ㅎㅂ', 'ㅇㅎㅂ']) {
    let accesses = 0;
    const tab = new Proxy({}, {get() {accesses++; throw new Error('browser access forbidden for excluded listing');}});
    const marked = {...item, title: `펌) ${marker}) 제목`, sourceListingPage: 4, sourceListingObservedAt: '2026-10-09T01:00:00Z', sourceListingPhase: 'initial'};
    const result = await load().collectPost(tab, marked);
    assert.equal(accesses, 0);
    assert.equal(result.status, 'policy_excluded');
    assert.equal(result.reason, 'known_listing_nsfw_marker');
    assert.equal(result.attempts.length, 0);
    assert.equal(result.commentCount, null);
    assert.equal(result.kCount, null);
    assert.equal(result.thresholdQualified, null);
    assert.equal(result.candidate, false);
    assert.equal(result.dateVerified, false);
    assert.equal(result.listingEvidence[0].title, marked.title);
    assert.equal(result.listingEvidence[0].url, marked.url);
    assert.equal(result.listingEvidence[0].marker, marker);
    assert.equal(result.listingEvidence[0].sourceListingPage, 4);
    assert.equal(result.listingEvidence[0].sourceListingObservedAt, marked.sourceListingObservedAt);
  }
});

test('non-marker consonant run does not trigger a listing-policy false positive', async () => {
  const {tab, calls} = tabMock();
  const result = await load().collectPost(tab, {...item, title: 'ㅎㅎㅎㅂㅋㅋ'});
  assert.equal(result.status, 'observed');
  assert.ok(calls.evaluate > 0);
});

test('Python and JavaScript title rule definitions and shared cases remain identical', () => {
  const macro = load();
  const pythonRules = JSON.parse(execFileSync('python', ['-B', '-c', 'import json,core; print(json.dumps([{"code":c,"pattern":p} for c,p in core.TITLE_SAFETY_RULES], ensure_ascii=False))'], {cwd: path.join(__dirname, '../src'), encoding: 'utf8', env: {...process.env, PYTHONDONTWRITEBYTECODE: '1'}}));
  assert.deepEqual(JSON.parse(JSON.stringify(macro.listingTitleSafetyRules)), pythonRules);
  const cases = JSON.parse(fs.readFileSync(path.join(__dirname, 'title-safety-cases.json'), 'utf8'));
  for (const fixture of cases) {
    assert.deepEqual(JSON.parse(JSON.stringify(macro.classifyListingTitle(fixture.title))), fixture.expected);
  }
});

test('all existing title safety rules exclude before any browser access', async () => {
  const cases = [
    ['차에서 섹스하다…', 'sexual_title', '섹스'],
    ['참수 영상', 'graphic_or_death_title', '참수'],
    ['불륜 이야기', 'private_allegation_title', '불륜'],
  ];
  for (const [title, code, matchedText] of cases) {
    let accesses = 0;
    const tab = new Proxy({}, {get() {accesses++; throw new Error('browser access forbidden');}});
    const result = await load().collectPost(tab, {...item, title});
    assert.equal(accesses, 0);
    assert.equal(result.status, 'policy_excluded');
    assert.equal(result.reason, 'known_listing_title_safety_exclusion');
    assert.deepEqual(JSON.parse(JSON.stringify(result.matchedRules)), [{code, matchedText}]);
    assert.equal(result.listingEvidence[0].title, title);
    assert.equal(result.commentCount, null);
    assert.equal(result.kCount, null);
    assert.equal(result.listedAt, null);
  }
});

test('count mismatch retains observed header and partial native IDs dates counts without comment text', async () => {
  const {macro, tab, calls} = parserTab({commentCountText: '2'});
  const result = await macro.collectPost(tab, item);
  assert.equal(result.status, 'failed');
  assert.equal(result.title, '제목');
  assert.equal(result.listedAtRaw, '2026-10-08 12:00:00');
  assert.equal(result.id, '100');
  assert.equal(result.commentsExpected, 2);
  assert.equal(result.commentsAllSelected, true);
  assert.equal(result.commentCounts.length, 1);
  assert.equal(result.commentCounts[0].id, 'native-7');
  assert.equal(result.commentCounts[0].date, '2026-10-08 12:30:00');
  assert.equal(result.commentCounts[0].kCount, 11);
  assert.deepEqual(Object.keys(result.commentCounts[0]).sort(), ['date', 'id', 'kCount']);
  assert.ok(result.headerEvidenceObservedAt);
  assert.ok(result.commentEvidenceObservedAt);
  assert.equal(result.headerObservations.length, 2);
  assert.equal(result.attempts.length, 2);
  assert.equal(calls.evaluate, 4, 'no extra header or comment requests');
  assert.equal(calls.reload, 1);
  const normalized = JSON.parse(execFileSync('python', ['-B', '-c', 'import json,sys,core; r=core.normalize(json.load(sys.stdin),core.utc("2026-10-08T01:00:00Z"),core.utc("2026-10-09T01:00:00Z")); print(json.dumps(r))'], {cwd: path.join(__dirname, '../src'), input: JSON.stringify(result), encoding: 'utf8', env: {...process.env, PYTHONDONTWRITEBYTECODE: '1'}}));
  assert.equal(normalized.inWindow, true);
  assert.equal(normalized.observedKCount, 11);
  assert.equal(normalized.kCount, null);
  assert.equal(normalized.thresholdQualified, true);
  assert.equal(normalized.thresholdEvidence, 'observed_lower_bound');
  assert.equal(normalized.knownLiteralKMinimum, 11);
  assert.equal(normalized.candidateVerificationHeld, true);
  assert.equal(normalized.inspectionComplete, false);
});

test('readiness failure retains observed header without inventing native comment rows', async () => {
  const {tab, calls} = tabMock();
  tab.playwright.evaluate = async () => {
    calls.evaluate++;
    return {...presence, id: '100', url: item.url, title: '관찰된 제목', listedAtRaw: '2026-10-08 12:00:00', observedAt: '2026-10-09T01:00:00Z'};
  };
  tab.playwright.locator = selector => ({
    click: async () => {calls.clicks.push(selector);}, filter() {return this;},
    waitFor: async () => {if(selector==='body')return;throw new Error('numeric count readiness timeout');},
  });
  const result = await load().collectPost(tab, item);
  assert.equal(result.status, 'failed');
  assert.equal(result.title, '관찰된 제목');
  assert.equal(result.listedAtRaw, '2026-10-08 12:00:00');
  assert.equal(result.commentCounts, undefined);
  assert.equal(calls.evaluate, 2);
});

test('a later missing header does not erase a previously observed exact date', async () => {
  const {tab, calls} = tabMock();
  let index = 0;
  tab.playwright.evaluate = async () => {
    calls.evaluate++;
    return [
      {...presence, title: '관찰된 제목', listedAtRaw: '2026-10-08 12:00:00', observedAt: '2026-10-09T01:00:00Z'},
      {expected: 2, commentsAllSelected: true, observedAt: '2026-10-09T01:00:01Z', comments: [{id: 'native-1', date: '2026-10-08 12:30:00', kCount: 11}]},
      {title: null, body: false, listedAtRaw: null, observedAt: '2026-10-09T01:00:02Z', error: 'header missing'},
    ][index++];
  };
  const result = await load().collectPost(tab, item);
  assert.equal(result.status, 'blocked_or_missing');
  assert.equal(result.title, '관찰된 제목');
  assert.equal(result.listedAtRaw, '2026-10-08 12:00:00');
  assert.equal(result.commentCounts[0].kCount, 11);
  assert.equal(result.headerObservations.length, 2);
  assert.equal(result.headerObservations[1].listedAtRaw, null);
  assert.equal(calls.evaluate, 3);
});

test('terminal browser-runtime timeout chains request a batch pause after bounded retry', async () => {
  for (const message of ['Page.enable timed out', 'Runtime.evaluate timed out', 'CDP attach timed out', 'protocol transport timeout']) {
    const {tab, calls} = tabMock();
    tab.playwright.evaluate = async () => {calls.evaluate++; throw new Error(message);};
    const result = await load().collectPost(tab, item);
    assert.equal(result.status, 'failed');
    assert.equal(result.pauseReason, 'browser_runtime_failure');
    assert.equal(result.stopBatch, true);
    assert.equal(result.attempts.length, 2);
    assert.equal(calls.evaluate, 2);
    assert.equal(calls.reload, 1);
  }
});

test('runtime failure during recovery returns pause metadata without another browser attempt', async () => {
  const {tab, calls} = tabMock();
  tab.playwright.evaluate = async () => {calls.evaluate++; throw new Error('Page.enable timed out');};
  tab.playwright.domSnapshot = async () => {calls.snapshots++; throw new Error('Runtime.evaluate timed out');};
  const result = await load().collectPost(tab, item);
  assert.equal(result.status, 'failed');
  assert.equal(result.pauseReason, 'browser_runtime_failure');
  assert.equal(result.stopBatch, true);
  assert.equal(calls.evaluate, 1);
  assert.equal(calls.snapshots, 1);
  assert.equal(calls.reload, 0);
});

test('slice stops on runtime pause before throttle or another post', async () => {
  const {tab, calls} = tabMock();
  tab.playwright.evaluate = async () => {calls.evaluate++; throw new Error('Page.enable timed out');};
  const results = await load().collectSlice(tab, [item, {...item, id: '101', url: 'https://aagag.com/issue/?idx=101'}]);
  assert.equal(results.length, 1);
  assert.equal(results[0].stopBatch, true);
  assert.equal(calls.evaluate, 2);
  assert.deepEqual(calls.waits, []);
  assert.deepEqual(calls.goto, []);
});

test('success on retry after a runtime timeout does not pause the batch', async () => {
  const {tab, calls} = tabMock();
  let index = 0;
  tab.playwright.evaluate = async () => {
    calls.evaluate++;
    if (index++ === 0) throw new Error('Runtime.evaluate timed out');
    return [presence, preliminary, data][index - 2];
  };
  const result = await load().collectPost(tab, item);
  assert.equal(result.status, 'observed');
  assert.equal(result.stopBatch, undefined);
  assert.equal(result.pauseReason, undefined);
  assert.equal(calls.reload, 1);
});

test('generic record failure remains local and does not stop later records', async () => {
  const {tab, calls} = tabMock();
  let index = 0;
  tab.playwright.evaluate = async () => {
    calls.evaluate++;
    if (index++ < 2) throw new Error('generic extraction failure');
    return [{...presence,id:'101',url:'https://aagag.com/issue/?idx=101'}, preliminary, {...data,id:'101',url:'https://aagag.com/issue/?idx=101'}][index - 3];
  };
  const results = await load().collectSlice(tab, [item, {...item, id: '101', url: 'https://aagag.com/issue/?idx=101'}]);
  assert.equal(results.length, 2);
  assert.equal(results[0].status, 'failed');
  assert.equal(results[0].stopBatch, undefined);
  assert.equal(results[0].pauseReason, undefined);
  assert.equal(results[1].status, 'observed');
  assert.deepEqual(calls.waits, [3000, 3000]);
});

test('normal native count mismatch does not become a systemic runtime pause', async () => {
  const {macro, tab} = parserTab({commentCountText: '2'});
  const result = await macro.collectPost(tab, item);
  assert.equal(result.status, 'failed');
  assert.match(result.error, /Native comment count not ready or incomplete/);
  assert.equal(result.stopBatch, undefined);
  assert.equal(result.pauseReason, undefined);
});

test('unrelated timeout and non-timeout runtime messages do not combine into a false systemic pause', () => {
  const result = load().finalizeCollectorFailure({attempts: [{error: 'Runtime.evaluate script failed'}]}, new Error('native count readiness timeout'));
  assert.equal(result.status, 'failed');
  assert.equal(result.stopBatch, undefined);
  assert.equal(result.pauseReason, undefined);
});

test('bounded body attachment readiness precedes the first presence evaluation', async () => {
  const {tab, calls} = tabMock();
  const evaluate = tab.playwright.evaluate;
  tab.playwright.evaluate = async fn => {
    if (calls.evaluate === 0) {
      const bodyWait = calls.readiness.find(entry => entry.selector === 'body');
      assert.ok(bodyWait);
      assert.equal(bodyWait.options.state, 'attached');
      assert.equal(bodyWait.options.timeoutMs, 12000);
    }
    return evaluate(fn);
  };
  const result = await load().collectPost(tab, item);
  assert.equal(result.status, 'observed');
});

test('body attachment timeout stays explicit and never invents empty post or zero comments', async () => {
  const {tab, calls} = tabMock();
  tab.playwright.locator = selector => ({waitFor: async () => {assert.equal(selector, 'body'); throw new Error('body attachment readiness timeout');}});
  const result = await load().collectPost(tab, item);
  assert.equal(result.status, 'failed');
  assert.equal(result.documentReadiness.state, 'document_not_ready');
  assert.equal(result.documentReadiness.reason, 'body_attachment_wait_failed');
  assert.equal(result.commentCounts, undefined);
  assert.equal(result.commentsExpected, undefined);
  assert.equal(result.kCount, undefined);
  assert.equal(result.attempts.length, 2);
  assert.equal(calls.evaluate, 0);
  assert.equal(result.stopBatch, undefined);
});

test('body disappearing after the wait has null-safe diagnostics and explicit not-ready status', async () => {
  const macro = load({location: {href: item.url}, document: {body: null, readyState: 'loading', querySelector: () => null}});
  const {tab, calls} = tabMock();
  tab.playwright.evaluate = async fn => {calls.evaluate++; return fn();};
  const result = await macro.collectPost(tab, item);
  assert.equal(result.status, 'failed');
  assert.equal(result.documentReadiness.state, 'document_not_ready');
  assert.equal(result.documentReadiness.reason, 'body_absent_after_wait');
  assert.match(result.error, /Document not ready/);
  assert.doesNotMatch(result.error, /TypeError/);
  assert.equal(result.commentCounts, undefined);
  assert.equal(result.commentsExpected, undefined);
  assert.equal(result.headerObservations.length, 2);
  assert.equal(result.headerObservations[0].documentBodyPresent, false);
  assert.equal(calls.evaluate, 2);
});

test('attached but loading document is distinct from loaded missing content', async () => {
  for (const readyState of ['loading', 'complete']) {
    const macro = load({location: {href: item.url}, document: {body: {innerText: 'header unavailable'}, readyState, querySelector: () => null}});
    const {tab} = tabMock();
    tab.playwright.evaluate = async fn => fn();
    const result = await macro.collectPost(tab, item);
    assert.equal(result.status, readyState === 'loading' ? 'failed' : 'blocked_or_missing');
    assert.equal(result.documentReadiness.state, readyState === 'loading' ? 'document_not_ready' : 'loaded_missing_content');
    assert.equal(result.commentCounts, undefined);
    assert.equal(result.commentsExpected, undefined);
  }
});

test('retry body-readiness failure preserves earlier exact header and partial count evidence', async () => {
  const {tab, calls} = tabMock();
  let read = 0, bodyWaits = 0;
  const originalLocator = tab.playwright.locator;
  tab.playwright.locator = selector => {
    if (selector !== 'body') return originalLocator(selector);
    return {waitFor: async () => {if (++bodyWaits === 2) throw new Error('body attachment readiness timeout');}};
  };
  tab.playwright.evaluate = async () => {
    calls.evaluate++;
    return [
      {...presence, id: '100', title: '관찰된 제목', listedAtRaw: '2026-10-08 12:00:00', observedAt: '2026-10-09T01:00:00Z'},
      {expected: 2, commentsAllSelected: true, observedAt: '2026-10-09T01:00:01Z', comments: [{id: 'native-1', date: '2026-10-08 12:30:00', kCount: 11}]},
    ][read++];
  };
  const result = await load().collectPost(tab, item);
  assert.equal(result.status, 'failed');
  assert.equal(result.documentReadiness.state, 'document_not_ready');
  assert.equal(result.title, '관찰된 제목');
  assert.equal(result.listedAtRaw, '2026-10-08 12:00:00');
  assert.equal(result.commentsExpected, 2);
  assert.equal(result.commentCounts[0].kCount, 11);
  assert.equal(result.headerObservations.length, 1);
  assert.equal(calls.evaluate, 2);
});

test('CDP command-dispatch deadline pauses a terminal failure even when the secondary error differs', async () => {
  const {tab, calls} = tabMock();
  let attempt = 0;
  tab.playwright.evaluate = async () => {
    calls.evaluate++;
    if (attempt++ === 0) throw new Error('CDP operation exceeded its deadline before command dispatch');
    throw new TypeError('Cannot read properties of null');
  };
  const result = await load().collectPost(tab, item);
  assert.equal(result.status, 'failed');
  assert.match(result.error, /TypeError/);
  assert.equal(result.pauseReason, 'browser_runtime_failure');
  assert.equal(result.stopBatch, true);
  assert.equal(result.attempts.length, 2);
  assert.equal(calls.reload, 1);
});

test('an ordinary deadline without the exact CDP transport phrase stays a generic failure', () => {
  const result = load().finalizeCollectorFailure({attempts: []}, new Error('source extraction exceeded its deadline before processing'));
  assert.equal(result.status, 'failed');
  assert.equal(result.stopBatch, undefined);
});

for (const reason of ['approval-checker denied action','User canceled tool call','Permission denied']) test('no recovery browser call after '+reason, async()=>{const {tab,calls}=tabMock();tab.playwright.evaluate=async()=>{calls.evaluate++;throw new Error(reason)};const r=await load().collectPost(tab,item);assert.equal(r.stopBatch,true);assert.equal(calls.evaluate,1);assert.equal(calls.snapshots,0);assert.equal(calls.reload,0)});
test('redirected identity fails closed',async()=>{const {tab,calls}=tabMock();tab.playwright.evaluate=async()=>({...presence,id:'999'});const r=await load().collectPost(tab,item);assert.equal(r.pauseReason,'observed_identity_mismatch');assert.equal(calls.clicks.length,0)});
test('invalid requested origin never touches browser',async()=>{const tab=new Proxy({}, {get(){throw new Error('touched')}});const r=await load().collectPost(tab,{...item,url:'https://evil.test/issue/?idx=100'});assert.equal(r.pauseReason,'invalid_requested_identity')});
test('missing final counters remain null rather than zero', async()=>{
 const {macro,tab}=parserTab();const original=tab.playwright.evaluate;let count=0;
 tab.playwright.evaluate=async fn=>{count++;if(count===3){vm.runInNewContext('0');}
   const out=await original(fn);return out;};
 // Exercise exact callback with changing DOM after preliminary numeric readiness.
 const elements=new Map([['h1.title',{innerText:'제목'}],['#vContent',{}],['#comment_sort [sort=all]',{}],['#comment_sort [sort=all].on',{}],['#comment_cnt strong',{textContent:'1'}]]);
 let evaluation=0;const c=load({location:{href:item.url},document:{body:{innerText:'body'},querySelector:s=>elements.get(s)||null,querySelectorAll:s=>s==='#comment .cmt[w_idx]'?[{getAttribute:()=> '1',querySelector:s=>s==='.content'?{innerText:'ㅋㅋㅋㅋㅋㅋㅋㅋㅋㅋㅋ'}:null}]:[]}});
 const m=tabMock();m.tab.playwright.evaluate=async fn=>{if(++evaluation===3)elements.delete('#comment_cnt strong');return fn();};
 const r=await c.collectPost(m.tab,item);assert.equal(r.commentsExpected,null);assert.equal(r.sourcesExpected,null);
});
test('denial during recovery stops batch without second attempt',async()=>{
 const {tab,calls}=errorTab();tab.playwright.domSnapshot=async()=>{calls.snapshots++;throw new Error('approval checker denied')};
 const r=await load().collectPost(tab,item);assert.equal(r.stopBatch,true);assert.equal(calls.reload,0);
});
test('missing native comment content is unknown and cannot exclude below threshold',async()=>{
 const {tab,calls}=tabMock();let i=0;tab.playwright.evaluate=async()=>i++%2?{expected:1,comments:[{id:'1',kCount:null}]}:presence;
 const r=await load().collectPost(tab,item);assert.equal(r.status,'failed');assert.equal(r.commentCounts[0].kCount,null);assert.equal(r.verificationScope,undefined);
});
