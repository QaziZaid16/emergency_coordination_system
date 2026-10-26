import { request } from '../api/client';
import { validateApiOrigin } from '../api/config';

export type Account = { id: string; email: string; display_name: string; role: 'admin' | 'super_admin' | string; permissions: string[] };
export type Session = { origin: string; token: string; account: Account };
const KEY = 'ecs-react-admin-session';

export function saveSession(session: Session, storage: Storage = sessionStorage) { storage.setItem(KEY, JSON.stringify(session)); }
export function clearSession(storage: Storage = sessionStorage) { storage.removeItem(KEY); }
export function readSession(storage: Storage = sessionStorage): Session | null {
  try {
    const value = JSON.parse(storage.getItem(KEY) || 'null');
    return value?.origin && value?.token && value?.account ? { ...value, origin: validateApiOrigin(value.origin, import.meta.env.DEV) } : null;
  } catch { clearSession(storage); return null; }
}
export function hasPermission(account: Account, permission: string): boolean {
  return account.role === 'super_admin' || account.permissions?.includes(permission) === true;
}
export async function signIn(origin: string, email: string, password: string): Promise<Session> {
  const result = await request<{ access_token: string; user: Account }>(origin, '/auth/login', { method: 'POST', body: JSON.stringify({ email: email.trim(), password, remember_me: false }) });
  if (!['admin', 'super_admin'].includes(result.user.role)) throw new Error('This account does not have administrative access.');
  return { origin, token: result.access_token, account: result.user };
}
export async function verifySession(session: Session): Promise<Session> {
  const account = await request<Account>(session.origin, '/auth/me', { token: session.token });
  if (!['admin', 'super_admin'].includes(account.role)) throw new Error('This account does not have administrative access.');
  return { ...session, account };
}
export async function signOut(session: Session) {
  try { await request<void>(session.origin, '/auth/logout', { method: 'POST', token: session.token }); } finally { clearSession(); }
}
