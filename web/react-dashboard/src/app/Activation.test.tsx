import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Activation, takeInvitationToken } from './Activation';

beforeEach(() => {
  vi.unstubAllEnvs();
  vi.stubGlobal('fetch', vi.fn());
});

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

describe('responder invitation activation', () => {
  it('prefers the fragment token and scrubs tokens while retaining unrelated URL state', () => {
    let cleanUrl = '';
    const token = takeInvitationToken(
      { pathname: '/activate.html', search: '?token=query-token&campaign=mail', hash: '#token=fragment-token&source=email' },
      { replaceState: (_state, _title, url) => { cleanUrl = String(url); } },
    );
    expect(token).toBe('fragment-token');
    expect(cleanUrl).toBe('/activate.html?campaign=mail#source=email');
  });

  it('accepts legacy query-token links and removes the token before rendering', () => {
    let cleanUrl = '';
    const token = takeInvitationToken(
      { pathname: '/activate', search: '?token=legacy-token&from=invite', hash: '' },
      { replaceState: (_state, _title, url) => { cleanUrl = String(url); } },
    );
    expect(token).toBe('legacy-token');
    expect(cleanUrl).toBe('/activate?from=invite');
  });

  it('does not show a password form when the invitation token is missing', () => {
    render(<Activation token="" />);
    expect(screen.getByRole('img', { name: 'IERCS' })).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent(/invitation link is incomplete/i);
    expect(screen.queryByRole('button', { name: 'Activate account' })).not.toBeInTheDocument();
  });

  it('requires matching passwords and posts the existing invitation contract once', async () => {
    const fetch = vi.mocked(globalThis.fetch);
    fetch.mockResolvedValue(new Response(JSON.stringify({ activated: true, email: 'responder@example.org' }), { status: 200 }));
    render(<Activation token="one-time-invitation-token" />);
    fireEvent.change(screen.getByLabelText('Service URL'), { target: { value: 'http://127.0.0.1:8000' } });
    fireEvent.change(screen.getByLabelText('New password'), { target: { value: 'long-enough-password' } });
    fireEvent.change(screen.getByLabelText('Confirm password'), { target: { value: 'different-password' } });
    fireEvent.click(screen.getByRole('button', { name: 'Activate account' }));
    expect(screen.getByRole('status')).toHaveTextContent(/passwords do not match/i);
    expect(fetch).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText('Confirm password'), { target: { value: 'long-enough-password' } });
    fireEvent.click(screen.getByRole('button', { name: 'Activate account' }));
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    expect(fetch).toHaveBeenCalledWith('http://127.0.0.1:8000/api/v1/auth/accept-invitation', expect.objectContaining({
      method: 'POST',
      redirect: 'error',
      body: JSON.stringify({ token: 'one-time-invitation-token', password: 'long-enough-password' }),
    }));
    expect(await screen.findByRole('status')).toHaveTextContent(/account activated/i);
    expect(screen.queryByRole('button', { name: 'Activate account' })).not.toBeInTheDocument();
  });

  it('uses the configured HTTPS API origin without exposing a manual origin field', async () => {
    vi.stubEnv('VITE_ECS_API_ORIGIN', 'https://api.coordination-services.org');
    const fetch = vi.mocked(globalThis.fetch);
    fetch.mockResolvedValue(new Response(JSON.stringify({ activated: true }), { status: 200 }));
    render(<Activation token="configured-token" />);
    expect(screen.queryByLabelText('Service URL')).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('New password'), { target: { value: 'long-enough-password' } });
    fireEvent.change(screen.getByLabelText('Confirm password'), { target: { value: 'long-enough-password' } });
    fireEvent.click(screen.getByRole('button', { name: 'Activate account' }));
    await waitFor(() => expect(fetch).toHaveBeenCalledWith('https://api.coordination-services.org/api/v1/auth/accept-invitation', expect.anything()));
  });

  it('shows the API error and keeps the form available when activation fails', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValue(new Response(JSON.stringify({ detail: 'This invitation is invalid or expired.' }), { status: 400 }));
    render(<Activation token="expired-token" />);
    fireEvent.change(screen.getByLabelText('Service URL'), { target: { value: 'http://127.0.0.1:8000' } });
    fireEvent.change(screen.getByLabelText('New password'), { target: { value: 'long-enough-password' } });
    fireEvent.change(screen.getByLabelText('Confirm password'), { target: { value: 'long-enough-password' } });
    fireEvent.click(screen.getByRole('button', { name: 'Activate account' }));
    expect(await screen.findByRole('status')).toHaveTextContent(/invalid or expired/i);
    expect(screen.getByRole('button', { name: 'Activate account' })).toBeInTheDocument();
  });
});
