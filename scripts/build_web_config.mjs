import { writeFile } from 'node:fs/promises';

const apiBaseUrl = (process.env.ECS_API_BASE_URL || '').trim().replace(/\/+$/, '');
const required = process.argv.includes('--required');

if (required && !apiBaseUrl) {
  throw new Error('ECS_API_BASE_URL must be configured for a production web build.');
}
if (apiBaseUrl) {
  let url;
  try {
    url = new URL(apiBaseUrl);
  } catch {
    throw new Error('ECS_API_BASE_URL must be an absolute HTTPS service origin.');
  }
  if (
    url.protocol !== 'https:' ||
    !url.hostname ||
    (url.pathname !== '/' && url.pathname !== '') ||
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    /(^|\.)example(\.|$)|(^|\.)(test|invalid|localhost)$|your-api-host/i.test(url.hostname)
  ) {
    throw new Error('ECS_API_BASE_URL must be a real HTTPS service URL, not a placeholder.');
  }
}

const source = `window.ECS_CONFIG = Object.freeze(${JSON.stringify({ apiBaseUrl })});\n`;
await writeFile(new URL('../web/admin/config.js', import.meta.url), source, 'utf8');
console.log(`Admin web configuration prepared (${apiBaseUrl ? 'HTTPS API configured' : 'local manual API entry'}).`);
