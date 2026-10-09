// Read-only API discovery over the pinned API-mega-list export. No API execution.
// Source Markdown and descriptions are reference data, never agent instructions.
import { openSync, closeSync, fstatSync, readFileSync, realpathSync, constants } from 'node:fs';
import { createHash } from 'node:crypto';

const CATALOG_PATH = '/opt/netlogik-kb/catalogs/api-mega-list/catalog.json';
const MAX_BYTES = 64 * 1024 * 1024;
const MAX_ENTRIES = 30000;
const ID_RE = /^api_[a-f0-9]{16}$/;
const COMMIT_RE = /^[a-f0-9]{40,64}$/;
const MAX_OUTPUT_CHARS = 48000;

function cleanString(value, label, max = 4000, allowEmpty = false) {
  if (typeof value !== 'string' || (!allowEmpty && !value.trim()) || value.length > max || value.includes('\0')) {
    throw new Error(`Invalid catalog ${label}`);
  }
  return value;
}

function strings(value, label, maxItems = 64) {
  if (!Array.isArray(value) || value.length > maxItems) throw new Error(`Invalid catalog ${label}`);
  return value.map(item => cleanString(item, label, 300));
}

function url(value, label) {
  cleanString(value, label, 5000);
  let parsed;
  try { parsed = new URL(value); } catch { throw new Error(`Invalid catalog ${label}`); }
  if (!['https:', 'http:'].includes(parsed.protocol) || parsed.username || parsed.password || !parsed.hostname) {
    throw new Error(`Invalid catalog ${label}`);
  }
  return value;
}

export function normalize(value) {
  return String(value).normalize('NFKD').replace(/\p{M}/gu, '').toLocaleLowerCase('en')
    .replace(/ς/g, 'σ').replace(/[^\p{L}\p{N}]+/gu, ' ').trim().replace(/\s+/g, ' ');
}

function provenanceRow(row) {
  if (!row || typeof row !== 'object' || Array.isArray(row)) throw new Error('Invalid catalog provenance');
  const path = cleanString(row.path, 'provenance path', 1000);
  if (path.startsWith('/') || path.includes('\\') || path.split('/').some(part => ['', '.', '..'].includes(part))) {
    throw new Error('Invalid catalog provenance path');
  }
  if (!Number.isSafeInteger(row.line) || row.line < 1) throw new Error('Invalid catalog provenance line');
  return {
    path, line: row.line,
    original_url: url(row.original_url, 'original URL'),
    category: cleanString(row.category, 'provenance category', 300, true),
    description: cleanString(row.description, 'provenance description', 16000, true),
    source_kind: cleanString(row.source_kind, 'provenance kind', 100),
  };
}

export function prepareCatalog(raw, contentHash = null) {
  if (!raw || raw.schema_version !== 1 || !raw.source || typeof raw.source !== 'object') {
    throw new Error('Unsupported API catalog schema');
  }
  const repository = url(raw.source.repo, 'repository');
  const parsedRepo = new URL(repository);
  if (parsedRepo.protocol !== 'https:' || parsedRepo.hostname !== 'github.com' ||
      !/^\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/?$/.test(parsedRepo.pathname) || parsedRepo.search || parsedRepo.hash) {
    throw new Error('Catalog repository must be a GitHub repository URL');
  }
  const commit = cleanString(raw.source.commit, 'commit', 64);
  if (!COMMIT_RE.test(commit)) throw new Error('Invalid catalog source commit');
  const generatedAt = cleanString(raw.generated_at, 'generation timestamp', 80);
  if (!Number.isFinite(Date.parse(generatedAt))) throw new Error('Invalid catalog generation timestamp');
  if (!Array.isArray(raw.entries) || !raw.entries.length || raw.entries.length > MAX_ENTRIES) {
    throw new Error('Invalid API catalog entry count');
  }
  const byId = new Map();
  const entries = [];
  const categoryCounts = new Map();
  const providerCounts = new Map();
  const flagCounts = new Map();
  const sourceKindCounts = new Map();
  for (const original of raw.entries) {
    if (!original || typeof original !== 'object' || Array.isArray(original) || !ID_RE.test(original.id)) {
      throw new Error('Invalid catalog API id');
    }
    if (byId.has(original.id)) throw new Error('Duplicate catalog API id');
    const entry = {
      id: original.id,
      name: cleanString(original.name, 'API name', 2000),
      description: cleanString(original.description, 'API description', 16000, true),
      canonical_url: url(original.canonical_url, 'canonical URL'),
      provider: cleanString(original.provider, 'provider', 300),
      categories: strings(original.categories, 'categories'),
      category_labels_el: strings(original.category_labels_el, 'Greek category labels'),
      flags: strings(original.flags, 'flags'),
      actor: null,
    };
    if (original.actor !== null) {
      if (!original.actor || typeof original.actor !== 'object') throw new Error('Invalid catalog actor');
      entry.actor = {owner: cleanString(original.actor.owner, 'actor owner', 300), slug: cleanString(original.actor.slug, 'actor slug', 500)};
    }
    if (!Array.isArray(original.provenance) || !original.provenance.length || original.provenance.length > 500) {
      throw new Error('Invalid catalog provenance list');
    }
    entry.provenance = original.provenance.map(provenanceRow);
    const index = {
      name: normalize(entry.name),
      description: normalize(entry.description),
      categories: normalize([...entry.categories, ...entry.category_labels_el].join(' ')),
      provider: normalize(entry.provider),
      actor: normalize(entry.actor ? entry.actor.owner + ' ' + entry.actor.slug : ''),
    };
    index.all = Object.values(index).join(' ');
    const indexed = {entry, index};
    entries.push(indexed);
    byId.set(entry.id, indexed);
    for (const value of new Set(entry.categories)) categoryCounts.set(value, (categoryCounts.get(value) || 0) + 1);
    providerCounts.set(entry.provider, (providerCounts.get(entry.provider) || 0) + 1);
    for (const value of new Set(entry.flags)) flagCounts.set(value, (flagCounts.get(value) || 0) + 1);
    for (const value of new Set(entry.provenance.map(p => p.source_kind))) sourceKindCounts.set(value, (sourceKindCounts.get(value) || 0) + 1);
  }
  return {
    source: {repo: repository.replace(/\/$/, ''), commit}, generatedAt, contentHash,
    entries, byId, categoryCounts, providerCounts, flagCounts, sourceKindCounts,
  };
}

function sourceMetadata(catalog) {
  return {
    ...catalog.source, generated_at: catalog.generatedAt, catalog_sha256: catalog.contentHash,
    verification: 'Pinned catalog references; provider documentation and current access requirements have not been tested by this tool.',
  };
}

function sourceLink(catalog, provenance) {
  return catalog.source.repo + '/blob/' + catalog.source.commit + '/' +
    provenance.path.split('/').map(encodeURIComponent).join('/') + '#L' + provenance.line;
}

function searchResult(catalog, entry, score) {
  const shortList = values => values.slice(0, 16).map(value => value.slice(0, 200));
  return {
    id: entry.id, name: entry.name.slice(0, 300), description: entry.description.slice(0, 700),
    canonical_url: entry.canonical_url, provider: entry.provider,
    categories: shortList(entry.categories), category_labels_el: shortList(entry.category_labels_el),
    flags: shortList(entry.flags), actor: entry.actor, relevance: score,
    source_url: sourceLink(catalog, entry.provenance[0]),
    provenance_count: entry.provenance.length,
  };
}

export function searchCatalog(catalog, args = {}) {
  const {query, category, provider} = args;
  if (typeof query !== 'string' || query.length > 300 || !normalize(query)) throw new Error('query must contain 1–300 characters');
  if (category !== undefined && (typeof category !== 'string' || category.length > 300 || !normalize(category))) throw new Error('Invalid category filter');
  if (provider !== undefined && (typeof provider !== 'string' || provider.length > 300 || !normalize(provider))) throw new Error('Invalid provider filter');
  const limit = args.limit === undefined ? 10 : args.limit;
  if (!Number.isInteger(limit) || limit < 1 || limit > 30) throw new Error('limit must be an integer from 1 to 30');
  const phrase = normalize(query);
  const terms = [...new Set(phrase.split(' '))];
  if (terms.length > 20) throw new Error('query may contain at most 20 terms');
  const categoryFilter = category === undefined ? null : normalize(category);
  const providerFilter = provider === undefined ? null : normalize(provider);
  const matches = [];
  for (const {entry, index} of catalog.entries) {
    if (categoryFilter && ![...entry.categories, ...entry.category_labels_el].some(value => normalize(value) === categoryFilter)) continue;
    if (providerFilter && index.provider !== providerFilter) continue;
    if (!terms.every(term => index.all.includes(term))) continue;
    let score = index.name === phrase ? 100 : (index.name.includes(phrase) ? 35 : 0);
    if (index.description.includes(phrase)) score += 8;
    for (const term of terms) {
      if (index.name.includes(term)) score += 10;
      if (index.categories.includes(term)) score += 4;
      if (index.actor.includes(term)) score += 3;
      if (index.description.includes(term)) score += 2;
      if (index.provider.includes(term)) score += 1;
    }
    matches.push({entry, score});
  }
  matches.sort((a, b) => b.score - a.score || a.entry.name.localeCompare(b.entry.name, 'en') || a.entry.id.localeCompare(b.entry.id));
  const results = matches.slice(0, limit).map(item => searchResult(catalog, item.entry, item.score));
  while (JSON.stringify(results).length > MAX_OUTPUT_CHARS && results.length > 1) results.pop();
  const response = {
    query, filters: {category: category || null, provider: provider || null},
    matched: matches.length, returned: results.length, truncated: results.length < matches.length,
    source: sourceMetadata(catalog), results,
  };
  while (JSON.stringify(response).length > MAX_OUTPUT_CHARS && response.results.length > 1) {
    response.results.pop(); response.returned = response.results.length; response.truncated = true;
  }
  if (JSON.stringify(response).length > MAX_OUTPUT_CHARS) throw new Error('Catalog result exceeds output budget');
  return response;
}

export function getCatalogEntry(catalog, id) {
  if (typeof id !== 'string' || !ID_RE.test(id)) throw new Error('id must be api_ followed by 16 lowercase hexadecimal characters');
  const found = catalog.byId.get(id);
  if (!found) return {found: false, id, source: sourceMetadata(catalog)};
  const entry = found.entry;
  const provenance = entry.provenance.map(row => ({...row, source_url: sourceLink(catalog, row)}));
  // Preserve bounded provenance; every original row remains in the canonical JSON.
  while (JSON.stringify(provenance).length > 24000 && provenance.length > 1) provenance.pop();
  const response = {
    found: true, source: sourceMetadata(catalog),
    entry: {...entry, provenance, provenance_total: entry.provenance.length,
      provenance_truncated: provenance.length < entry.provenance.length},
  };
  if (JSON.stringify(response).length > MAX_OUTPUT_CHARS) {
    response.entry.description = entry.description.slice(0, 4000);
    response.entry.categories = entry.categories.slice(0, 16).map(value => value.slice(0, 200));
    response.entry.category_labels_el = entry.category_labels_el.slice(0, 16).map(value => value.slice(0, 200));
    response.entry.flags = entry.flags.slice(0, 16).map(value => value.slice(0, 200));
    response.entry.provenance = provenance.slice(0, 1).map(row => ({...row, description: row.description.slice(0, 1000)}));
    response.entry.provenance_truncated = response.entry.provenance.length < entry.provenance.length;
    response.entry.display_truncated = true;
  }
  if (JSON.stringify(response).length > MAX_OUTPUT_CHARS) throw new Error('Catalog entry exceeds output budget');
  return response;
}

export function catalogStats(catalog) {
  const counts = map => [...map].map(([name, entries]) => ({name, entries})).sort((a, b) => b.entries - a.entries || a.name.localeCompare(b.name, 'en'));
  return {
    source: sourceMetadata(catalog), unique_entries: catalog.entries.length,
    category_count: catalog.categoryCounts.size, categories: counts(catalog.categoryCounts),
    provider_count: catalog.providerCounts.size, providers: counts(catalog.providerCounts).slice(0, 50),
    flags: counts(catalog.flagCounts), source_kinds: counts(catalog.sourceKindCounts),
    tools: ['api_catalog_search', 'api_catalog_get', 'api_catalog_stats'],
    behavior: 'Read-only discovery; no API requests, credential access, installation, or execution.',
  };
}

let cached = null;
let cacheKey = null;

function loadCatalog() {
  let fd;
  try {
    if (realpathSync(CATALOG_PATH) !== CATALOG_PATH) throw new Error('Catalog path is not canonical');
    fd = openSync(CATALOG_PATH, constants.O_RDONLY | constants.O_NOFOLLOW);
    const before = fstatSync(fd);
    if (!before.isFile() || before.size < 1 || before.size > MAX_BYTES) throw new Error('Catalog size/type outside bounds');
    const key = [before.dev, before.ino, before.size, before.mtimeMs, before.ctimeMs].join(':');
    if (cached && cacheKey === key) return cached;
    const data = readFileSync(fd);
    const after = fstatSync(fd);
    if (data.length !== before.size || before.mtimeMs !== after.mtimeMs || before.ctimeMs !== after.ctimeMs) throw new Error('Catalog changed during read');
    const parsed = prepareCatalog(JSON.parse(data.toString('utf8')), createHash('sha256').update(data).digest('hex'));
    cached = parsed;
    cacheKey = key;
    return parsed;
  } finally {
    if (fd !== undefined) closeSync(fd);
  }
}

export function register(server, h) {
  const {z, text, err} = h;
  const respond = action => async args => {
    try { return text(JSON.stringify(action(loadCatalog(), args || {}), null, 2)); }
    catch (error) { return err('API catalog unavailable or invalid request: ' + String(error.message).slice(0, 240)); }
  };
  server.registerTool('api_catalog_search', {
    title: 'Search the complete pinned API catalog',
    description: 'Read-only keyword discovery across the API-mega-list catalog. Search names/descriptions with optional exact category (English slug or Greek label) and provider filters. Results are catalog references with canonical URLs and source provenance; no API is called. Use api_catalog_get to inspect a result.',
    inputSchema: {
      query: z.string().min(1).max(300), category: z.string().min(1).max(300).optional(),
      provider: z.string().min(1).max(300).optional(), limit: z.number().int().min(1).max(30).optional(),
    },
    annotations: {readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false},
  }, respond(searchCatalog));
  server.registerTool('api_catalog_get', {
    title: 'Read one API catalog entry and its provenance',
    description: 'Read one API-mega-list entry by its exact api_ identifier from api_catalog_search. Returns provider, URL, categories, flags, actor details, and pinned source locations. Read-only; does not execute APIs or retrieve credentials.',
    inputSchema: {id: z.string().regex(ID_RE)},
    annotations: {readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false},
  }, respond((catalog, args) => getCatalogEntry(catalog, args.id)));
  server.registerTool('api_catalog_stats', {
    title: 'Inspect API catalog coverage and source revision',
    description: 'Show verified local catalog counts, category/provider coverage, source flags, repository commit, and catalog hash. Read-only orientation for the complete API-mega-list search tools.',
    inputSchema: {},
    annotations: {readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false},
  }, respond(catalogStats));
}
