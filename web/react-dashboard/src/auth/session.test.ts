import { describe, expect, it, vi } from 'vitest';
import { clearSession, hasPermission, readSession, saveSession, Session, signIn } from './session';

const admin:Session={origin:'https://api.coordination-services.org',token:'t',account:{id:'1',email:'a@b.org',display_name:'Admin',role:'admin',permissions:['view_incidents']}};
describe('session and permissions',()=>{
  it('stores and clears tab session state',()=>{const storage=sessionStorage;saveSession(admin,storage);expect(readSession(storage)).toEqual(admin);clearSession(storage);expect(readSession(storage)).toBeNull();});
  it('restores a loopback HTTP session in local development',()=>{const local={...admin,origin:'http://127.0.0.1:18081'};saveSession(local,sessionStorage);expect(readSession(sessionStorage)).toEqual(local);});
  it('allows Super Admin and checks Co-Admin permission lists',()=>{expect(hasPermission(admin.account,'view_incidents')).toBe(true);expect(hasPermission(admin.account,'manage_users')).toBe(false);expect(hasPermission({...admin.account,role:'super_admin'},'manage_users')).toBe(true);});
  it('uses the verified login request and rejects non-admin accounts',async()=>{const fetch=vi.spyOn(globalThis,'fetch').mockResolvedValueOnce(new Response(JSON.stringify({access_token:'tok',user:admin.account}),{status:200}));await expect(signIn(admin.origin,' a@b.org ','password123456')).resolves.toMatchObject({token:'tok'});expect(JSON.parse(String(fetch.mock.calls[0][1]?.body))).toEqual({email:'a@b.org',password:'password123456',remember_me:false});fetch.mockResolvedValueOnce(new Response(JSON.stringify({access_token:'x',user:{...admin.account,role:'user'}}),{status:200}));await expect(signIn(admin.origin,'x@y.org','password123456')).rejects.toThrow(/administrative access/);fetch.mockRestore();});
});
