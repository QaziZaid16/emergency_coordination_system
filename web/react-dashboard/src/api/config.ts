export function validateApiOrigin(value: string): string {
  let url: URL;
  try { url = new URL(value.trim()); } catch { throw new Error('Set VITE_ECS_API_ORIGIN to a valid HTTPS API origin.'); }
  if (url.protocol !== 'https:' || !url.hostname || url.username || url.password ||
      (url.pathname !== '/' && url.pathname !== '') || url.search || url.hash ||
      /(^|\.)example(\.|$)|(^|\.)(test|invalid|localhost)$|your-api-host|your-domain/i.test(url.hostname)) {
    throw new Error('The API configuration must be a real HTTPS origin without credentials, path, query, or fragment.');
  }
  return url.origin;
}

export function configuredApiOrigin(raw = import.meta.env.VITE_ECS_API_ORIGIN || ''): string {
  return validateApiOrigin(raw);
}

export function hasConfiguredApiOrigin(): boolean { return Boolean((import.meta.env.VITE_ECS_API_ORIGIN || '').trim()); }
