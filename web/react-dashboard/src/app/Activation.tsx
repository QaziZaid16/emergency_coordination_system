import { FormEvent, useState } from 'react';
import { hasConfiguredApiOrigin, configuredApiOrigin } from '../api/config';
import { request } from '../api/client';
const logoUrl = '/brand/official-logo.svg';

export function takeInvitationToken(location: Pick<Location, 'pathname' | 'search' | 'hash'>, history: Pick<History, 'replaceState'>): string {
  const query = new URLSearchParams(location.search);
  const hash = new URLSearchParams(location.hash.replace(/^#/, ''));
  const token = hash.get('token') || query.get('token') || '';
  hash.delete('token');
  query.delete('token');
  const queryText = query.toString();
  const hashText = hash.toString();
  history.replaceState(null, '', `${location.pathname}${queryText ? `?${queryText}` : ''}${hashText ? `#${hashText}` : ''}`);
  return token;
}

function loopbackHost(host: string) {
  return ['localhost', '127.0.0.1', '[::1]', '::1'].includes(host);
}

function activationOrigin(value: string): string {
  let target: URL;
  let page: URL;
  try {
    target = new URL(value.trim());
    page = new URL(window.location.href);
  } catch {
    throw new Error('Enter a valid API origin.');
  }
  if (!target.hostname || target.username || target.password || target.search || target.hash || (target.pathname !== '/' && target.pathname !== '')) {
    throw new Error('Use an API origin without credentials, paths, queries, or fragments.');
  }
  if (target.protocol === 'https:') return target.origin;
  if (target.protocol === 'http:' && page.protocol === 'http:' && loopbackHost(page.hostname) && loopbackHost(target.hostname)) return target.origin;
  throw new Error('HTTPS is required, except for loopback-only local development.');
}

function localActivationPage() {
  return window.location.protocol === 'http:' && loopbackHost(window.location.hostname);
}

export function Activation({ token }: { token:string }) {
  const configured = hasConfiguredApiOrigin();
  const [origin, setOrigin] = useState(() => {
    if (!configured) return '';
    try { return configuredApiOrigin(); } catch { return ''; }
  });
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [status, setStatus] = useState(() => {
    if (!token) return 'This invitation link is incomplete. Ask your administrator to send a new invitation.';
    if (configured) {
      try { configuredApiOrigin(); } catch (error) { return `Activation is unavailable: ${(error as Error).message}`; }
    } else if (!localActivationPage()) return 'Activation is unavailable because the API service is not configured.';
    return 'Set a password to complete your secure invitation.';
  });
  const [busy, setBusy] = useState(false);
  const [complete, setComplete] = useState(false);
  const canSubmit = Boolean(token) && !complete && (!configured || Boolean(origin)) && (configured || localActivationPage());

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (password !== confirmation) {
      setStatus('Passwords do not match.');
      return;
    }
    setBusy(true);
    try {
      const apiOrigin = configured ? configuredApiOrigin() : activationOrigin(origin);
      await request(apiOrigin, '/auth/accept-invitation', {
        method: 'POST',
        body: JSON.stringify({ token, password }),
      });
      setComplete(true);
      setStatus('Account activated. You can now sign in through the mobile app.');
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Activation failed.');
    } finally {
      setBusy(false);
    }
  }

  return <main className="login-screen"><section className="login-card" aria-labelledby="activation-title">
    <img className="login-logo" src={logoUrl} alt="Emergency Coordination" />
    <p className="eyebrow">RESPONDER ONBOARDING</p>
    <h1 id="activation-title">Activate your account</h1>
    <p className="muted" role="status" aria-live="polite">{status}</p>
    {token && !complete && (configured || localActivationPage()) && <form className="activation-form" onSubmit={submit}>
      {!configured && <label>Service URL<input aria-label="Service URL" type="url" value={origin} onChange={event => setOrigin(event.target.value)} placeholder="http://127.0.0.1:8000" required /></label>}
      <label>New password<input aria-label="New password" type="password" minLength={12} maxLength={128} autoComplete="new-password" value={password} onChange={event => setPassword(event.target.value)} required /></label>
      <label>Confirm password<input aria-label="Confirm password" type="password" minLength={12} maxLength={128} autoComplete="new-password" value={confirmation} onChange={event => setConfirmation(event.target.value)} required /></label>
      <button className="primary" disabled={busy || !canSubmit}>{busy ? 'Activating…' : 'Activate account'}</button>
    </form>}
  </section></main>;
}
