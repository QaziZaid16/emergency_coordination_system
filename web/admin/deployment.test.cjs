const test = require('node:test');
const assert = require('node:assert/strict');
const { existsSync, readFileSync } = require('node:fs');
const path = require('node:path');
const { apiOrigin, initialize, takeToken } = require('../activation');

const root = path.resolve(__dirname, '../..');
const config = JSON.parse(readFileSync(path.join(root, 'vercel.json'), 'utf8'));
const rewrites = new Map(config.rewrites.map(({ source, destination }) => [source, destination]));

test('static deployment root and required application routes resolve to checked-in pages', () => {
  assert.equal(config.outputDirectory, 'web');
  assert.equal(rewrites.get('/'), '/admin/index.html');
  assert.equal(rewrites.get('/index.html'), '/admin/index.html');
  assert.equal(rewrites.get('/admin'), '/admin/index.html');
  assert.equal(rewrites.get('/activate'), '/activate.html');
  for (const relativePath of [
    'web/admin/index.html',
    'web/admin/app.js',
    'web/admin/redesign.js',
    'web/admin/config.js',
    'web/admin/style.css',
    'web/admin/redesign.css',
    'web/activate.html',
    'web/activation.js',
    'web/assets/brand/official-logo.svg',
  ]) {
    assert.ok(existsSync(path.join(root, relativePath)), `missing output file: ${relativePath}`);
  }
});

test('static browser configuration contains no server credential fields', () => {
  const publicConfig = readFileSync(path.join(root, 'web/admin/config.js'), 'utf8');
  assert.doesNotMatch(
    publicConfig,
    /(?:JWT_SECRET|OPENROUTER_API_KEY|DATABASE_URL|SMTP_PASSWORD|POSTGRES_PASSWORD)/,
  );
  const builder = readFileSync(path.join(root, 'scripts/build_web_config.mjs'), 'utf8');
  assert.match(builder, /JSON\.stringify\(\{ apiBaseUrl \}\)/);
  assert.match(builder, /url\.pathname !== '\/'/);
});

test('dashboard and activation page local asset references resolve', () => {
  for (const page of ['web/admin/index.html', 'web/activate.html']) {
    const html = readFileSync(path.join(root, page), 'utf8');
    const references = [...html.matchAll(/(?:src|href)="([^"]+)"/g)]
      .map((match) => match[1])
      .filter((value) => value.startsWith('/') || value.startsWith('./') || value.startsWith('../'));
    for (const reference of references) {
      const resolved = reference.startsWith('/')
        ? path.join(root, 'web', reference.slice(1))
        : path.resolve(path.dirname(path.join(root, page)), reference);
      assert.ok(existsSync(resolved), `${page} references missing asset ${reference}`);
    }
  }
});

test('activation accepts HTTPS origins and loopback HTTP only for local development', () => {
  assert.equal(apiOrigin('https://api.example.org/', 'https://site.example.org/activate'), 'https://api.example.org');
  assert.equal(apiOrigin('http://127.0.0.1:8000', 'http://localhost:8080/activate'), 'http://127.0.0.1:8000');
  assert.equal(apiOrigin('http://[::1]:8000', 'http://localhost:8080/activate'), 'http://[::1]:8000');
  for (const [target, page] of [
    ['http://api.example.org', 'https://site.example.org/activate'],
    ['http://192.168.1.20:8000', 'http://localhost:8080/activate'],
    ['https://user:pass@api.example.org', 'https://site.example.org/activate'],
    ['https://api.example.org/path', 'https://site.example.org/activate'],
    ['https://api.example.org/?key=value', 'https://site.example.org/activate'],
    ['not a URL', 'https://site.example.org/activate'],
  ]) assert.throws(() => apiOrigin(target, page));
});

test('activation page removes invitation tokens and disallows unconfigured hosted targets', () => {
  const html = readFileSync(path.join(root, 'web/activate.html'), 'utf8');
  const activation = readFileSync(path.join(root, 'web/activation.js'), 'utf8');
  assert.match(html, /\/admin\/config\.js/);
  assert.match(activation, /history\.replaceState/);
  assert.match(activation, /redirect: 'error'/);
  assert.match(activation, /API service is not configured/);
});

test('activation token is read from the fragment and scrubbed before use', () => {
  let replacedUrl;
  const win = {
    location: {
      pathname: '/activate.html',
      search: '?campaign=demo',
      hash: '#token=fragment-token&source=email',
    },
    history: { replaceState: (_state, _title, url) => { replacedUrl = url; } },
  };
  assert.equal(takeToken(win), 'fragment-token');
  assert.equal(replacedUrl, '/activate.html?campaign=demo#source=email');
});

test('activation temporarily accepts and immediately scrubs query tokens for outstanding links', () => {
  let replacedUrl;
  const win = {
    location: { pathname: '/activate.html', search: '?token=legacy-token', hash: '' },
    history: { replaceState: (_state, _title, url) => { replacedUrl = url; } },
  };
  assert.equal(takeToken(win), 'legacy-token');
  assert.equal(replacedUrl, '/activate.html');
});

test('activation removes the token from hosted URLs and requires configured API origin', () => {
  const elements = {
    '#form': { removed: false, remove() { this.removed = true; }, addEventListener() {} },
    '#status': { textContent: '' },
    '#api': { value: '' },
    '#api-label': { hidden: false },
    '#password': { value: 'long-enough-password' },
    '#confirm': { value: 'long-enough-password' },
  };
  let replacedUrl;
  const win = {
    document: { querySelector: (selector) => elements[selector] },
    location: { href: 'https://site.example.org/activate?token=one-time&from=mail', search: '?token=one-time&from=mail', pathname: '/activate', hash: '' },
    history: { replaceState: (_state, _title, url) => { replacedUrl = url; } },
    ECS_CONFIG: undefined,
  };
  initialize(win);
  assert.equal(replacedUrl, '/activate?from=mail');
  assert.equal(elements['#form'].removed, true);
  assert.match(elements['#status'].textContent, /API service is not configured/);
});

test('configured activation posts once to its origin and rejects redirects', async () => {
  const elements = {
    '#form': { removed: false, handler: null, remove() { this.removed = true; }, addEventListener(_name, handler) { this.handler = handler; } },
    '#status': { textContent: '' },
    '#api': { value: '' },
    '#api-label': { hidden: false },
    '#password': { value: 'long-enough-password' },
    '#confirm': { value: 'long-enough-password' },
  };
  let request;
  const win = {
    document: { querySelector: (selector) => elements[selector] },
    location: { href: 'https://site.example.org/activate?token=one-time', search: '?token=one-time', pathname: '/activate', hash: '' },
    history: { replaceState() {} },
    ECS_CONFIG: { apiBaseUrl: 'https://api.example.org/' },
    fetch: async (url, options) => {
      request = { url, options };
      return { ok: true, json: async () => ({}) };
    },
  };
  initialize(win);
  assert.equal(elements['#api'].value, 'https://api.example.org');
  assert.equal(elements['#api-label'].hidden, true);
  await elements['#form'].handler({ preventDefault() {} });
  assert.equal(request.url, 'https://api.example.org/api/v1/auth/accept-invitation');
  assert.equal(request.options.redirect, 'error');
  assert.deepEqual(JSON.parse(request.options.body), { token: 'one-time', password: 'long-enough-password' });
  assert.equal(elements['#form'].removed, true);
});
