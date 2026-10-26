function isLoopback(hostname: string) {
  return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '[::1]';
}

export function validateApiOrigin(value: string, allowLocalHttp = false): string {
  let url: URL;
  try { url = new URL(value.trim()); } catch { throw new Error('Invalid API origin configuration.'); }
  const secure = url.protocol === 'https:';
  const localDevelopment = allowLocalHttp && url.protocol === 'http:' && isLoopback(url.hostname);
  if ((!secure && !localDevelopment) || !url.hostname || url.username || url.password ||
      (url.pathname !== '/' && url.pathname !== '') || url.search || url.hash ||
      (!localDevelopment && /(^|\.)example(\.|$)|(^|\.)(test|invalid|localhost)$|your-api-host|your-domain/i.test(url.hostname))) {
    throw new Error('Invalid API origin configuration.');
  }
  return url.origin;
}

export function configuredApiOrigin(raw = import.meta.env.VITE_ECS_API_ORIGIN || ''): string {
  if (!raw.trim()) throw new Error('API origin is not configured.');
  return validateApiOrigin(raw, import.meta.env.DEV);
}

export function hasConfiguredApiOrigin(): boolean { return Boolean((import.meta.env.VITE_ECS_API_ORIGIN || '').trim()); }
