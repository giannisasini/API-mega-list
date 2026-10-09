import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {prepareCatalog, searchCatalog, getCatalogEntry, catalogStats, normalize, register} from './api-catalog.mjs';

function entry(index, overrides = {}) {
  return {
    id: 'api_' + index.toString(16).padStart(16, '0'),
    name: 'Google Maps places search', description: 'Find hotels and businesses by location.',
    canonical_url: 'https://apify.com/example/maps-search', provider: 'apify',
    categories: ['maps-location'], category_labels_el: ['Χάρτες και τοποθεσία'],
    flags: [], actor: {owner: 'example', slug: 'maps-search'},
    provenance: [{path: 'lists/Maps.md', line: 12, original_url: 'https://apify.com/example/maps-search',
      category: 'maps-location', description: 'Places discovery.', source_kind: 'category'}],
    ...overrides,
  };
}

function fixture(entries = [entry(1)]) {
  return {schema_version: 1, source: {repo: 'https://github.com/example/API-mega-list', commit: 'a'.repeat(40)},
    generated_at: '2026-10-09T12:00:00Z', entries};
}

test('search, exact category/provider filters, normalized Greek, and canonical get', () => {
  const catalog = prepareCatalog(fixture([entry(1), entry(2, {name: 'Weather forecast', description: 'Rain and wind forecasts',
    categories: ['weather'], category_labels_el: ['Καιρός'], provider: 'weatherapi', actor: null})]));
  assert.equal(searchCatalog(catalog, {query: 'google maps'}).results[0].id, entry(1).id);
  assert.equal(searchCatalog(catalog, {query: 'google maps', provider: 'weatherapi'}).matched, 0);
  assert.equal(searchCatalog(catalog, {query: 'places', category: 'χαρτες και τοποθεσια'}).matched, 1);
  assert.equal(searchCatalog(catalog, {query: 'καιρος'}).results[0].id, entry(2).id);
  const found = getCatalogEntry(catalog, entry(1).id);
  assert.equal(found.entry.provenance[0].source_url, 'https://github.com/example/API-mega-list/blob/' + 'a'.repeat(40) + '/lists/Maps.md#L12');
  assert.equal(getCatalogEntry(catalog, 'api_ffffffffffffffff').found, false);
  assert.equal(normalize('ΚΑΙΡΌΣ'), normalize('καιροσ'));
});

test('sponsored flags remain visible and do not boost result ranking', () => {
  const catalog = prepareCatalog(fixture([entry(1), entry(2, {flags: ['sponsored']})]));
  const results = searchCatalog(catalog, {query: 'google maps'}).results;
  assert.equal(results[0].relevance, results[1].relevance);
  assert.deepEqual(results[1].flags, ['sponsored']);
  const stats = catalogStats(catalog);
  assert.equal(stats.unique_entries, 2);
  assert.deepEqual(stats.flags, [{name: 'sponsored', entries: 1}]);
});

test('user inputs cannot choose filesystem paths, URL requests, code, or unbounded output', () => {
  const catalog = prepareCatalog(fixture());
  for (const id of ['../secrets', '/etc/passwd', 'https://example.com', 'api_' + '0'.repeat(17)]) {
    assert.throws(() => getCatalogEntry(catalog, id));
  }
  for (const args of [{query: ''}, {query: '*'}, {query: 'x'.repeat(301)}, {query: 'maps', limit: 31},
    {query: 'maps', limit: 1.2}, {query: 'maps', category: '../'}, {query: 'maps', provider: ''}]) {
    assert.throws(() => searchCatalog(catalog, args));
  }
  assert.equal(searchCatalog(catalog, {query: '$(touch /tmp/probe)'}).matched, 0);
});

test('catalog schema rejects duplicates, credential URLs, script URLs, malformed provenance', () => {
  assert.throws(() => prepareCatalog(fixture([entry(1), entry(1)])));
  for (const canonical_url of ['file:///etc/passwd', 'javascript:alert(1)', 'https://user:secret@example.com']) {
    assert.throws(() => prepareCatalog(fixture([entry(1, {canonical_url})])));
  }
  for (const path of ['../root.md', '/etc/passwd', 'a//b.md', 'a\\b.md']) {
    const bad = entry(1); bad.provenance[0].path = path;
    assert.throws(() => prepareCatalog(fixture([bad])));
  }
});

test('register only three read-only tools and perform no source read on registration', () => {
  const registered = [];
  const chain = new Proxy({}, {get: () => () => chain});
  const h = {z: {string: () => chain, number: () => chain}, text: value => ({content: [{type: 'text', text: value}]}),
    err: value => ({content: [{type: 'text', text: value}], isError: true})};
  register({registerTool: (...args) => registered.push(args)}, h);
  assert.deepEqual(registered.map(row => row[0]), ['api_catalog_search', 'api_catalog_get', 'api_catalog_stats']);
  for (const [, definition, handler] of registered) {
    assert.equal(definition.annotations.readOnlyHint, true);
    assert.equal(definition.annotations.destructiveHint, false);
    assert.equal(definition.annotations.openWorldHint, false);
    assert.equal(typeof handler, 'function');
  }
});

test('candidate fits tool_write size and uses no shell, environment, dynamic source path, or network', () => {
  const code = readFileSync(new URL('./api-catalog.mjs', import.meta.url), 'utf8');
  assert.ok(code.length < 40000);
  assert.doesNotMatch(code, /child_process|\bfetch\s*\(|process\.env|\beval\s*\(|new Function/);
  assert.match(code, /const CATALOG_PATH = '\/opt\/netlogik-kb\/catalogs\/api-mega-list\/catalog\.json'/);
});
