import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, request } from './client';

afterEach(() => vi.unstubAllGlobals());
describe('API client', () => {
  it('sends bearer auth, JSON and rejects redirects', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response('{"ok":true}',{status:200})); vi.stubGlobal('fetch',fetch);
    await expect(request('https://api.example.org','/incidents',{token:'secret-token',method:'POST',body:'{}'})).resolves.toEqual({ok:true});
    const [,options]=fetch.mock.calls[0]; expect(options.redirect).toBe('error'); expect(options.headers.Authorization).toBe('Bearer secret-token'); expect(options.headers['Content-Type']).toBe('application/json');
  });
  it('lets the browser set multipart boundaries for dataset uploads', async () => {
    const fetch=vi.fn().mockResolvedValue(new Response('{"ok":true}',{status:200}));vi.stubGlobal('fetch',fetch);
    const body=new FormData();body.append('fema_file',new File(['zip'],'database.csv.zip'));body.append('earthquake_file',new File(['csv'],'earthquake_1995-2023.csv'));
    await expect(request('https://api.example.org','/admin/public-disaster-data/import',{method:'POST',body})).resolves.toEqual({ok:true});
    const [,options]=fetch.mock.calls[0];expect(options.body).toBe(body);expect(options.headers['Content-Type']).toBeUndefined();
  });
  it('returns null for 204 and exposes safe API errors', async () => {
    vi.stubGlobal('fetch',vi.fn().mockResolvedValueOnce(new Response(null,{status:204})).mockResolvedValueOnce(new Response('{"detail":"No access"}',{status:403})));
    await expect(request('https://api.example.org','/x')).resolves.toBeNull(); await expect(request('https://api.example.org','/x')).rejects.toMatchObject({status:403,message:'No access'} as Partial<ApiError>);
  });
  it('converts network failures to a useful message', async () => { vi.stubGlobal('fetch',vi.fn().mockRejectedValue(new TypeError('network'))); await expect(request('https://api.example.org','/x')).rejects.toThrow(/Could not reach/); });
});
