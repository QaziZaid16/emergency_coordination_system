import { describe, expect, it } from 'vitest';
import { validateApiOrigin } from './config';

describe('API origin validation', () => {
  it('accepts a real HTTPS origin and strips its trailing slash', () => expect(validateApiOrigin('https://api.coordination-services.org/')).toBe('https://api.coordination-services.org'));
  it.each(['http://api.example.org','https://user:pass@api.coordination-services.org','https://api.coordination-services.org/path','https://api.coordination-services.org/?x=1','https://api.coordination-services.org/#x','https://api.example.org','https://your-api-host.invalid'])('rejects %s', value => expect(() => validateApiOrigin(value)).toThrow());
});
