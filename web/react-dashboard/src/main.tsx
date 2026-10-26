import React from 'react';
import { createRoot } from 'react-dom/client';
import { Dashboard } from './app/Dashboard';
import { Activation, takeInvitationToken } from './app/Activation';
import './styles.css';

const isActivationRoute = ['/activate', '/activate.html'].includes(window.location.pathname);
const invitationToken = isActivationRoute ? takeInvitationToken(window.location, window.history) : '';
createRoot(document.getElementById('root')!).render(<React.StrictMode>{isActivationRoute ? <Activation token={invitationToken} /> : <Dashboard />}</React.StrictMode>);
