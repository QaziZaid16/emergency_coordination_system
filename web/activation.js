(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root && root.window === root) api.initialize(root);
})(typeof window === 'undefined' ? null : window, function () {
  function apiOrigin(value, pageUrl) {
    let target;
    let page;
    try {
      target = new URL(value);
      page = new URL(pageUrl);
    } catch {
      throw new Error('Enter a valid API origin.');
    }
    if (
      !target.hostname || target.username || target.password || target.search || target.hash ||
      (target.pathname !== '/' && target.pathname !== '')
    ) {
      throw new Error('Use an API origin without credentials, paths, queries, or fragments.');
    }
    if (target.protocol === 'https:') return target.origin;

    const loopback = (url) => ['localhost', '127.0.0.1', '[::1]', '::1'].includes(url.hostname);
    if (target.protocol === 'http:' && page.protocol === 'http:' && loopback(page) && loopback(target)) {
      return target.origin;
    }
    throw new Error('HTTPS is required, except for loopback-only local development.');
  }

  function takeToken(win) {
    const query = new URLSearchParams(win.location.search);
    const hash = win.location.hash.startsWith('#')
      ? win.location.hash.slice(1)
      : win.location.hash;
    const fragment = new URLSearchParams(hash);
    const token = fragment.get('token') || query.get('token');
    fragment.delete('token');
    query.delete('token');
    const remainingQuery = query.toString();
    const remainingFragment = fragment.toString();
    win.history.replaceState(
      null,
      '',
      `${win.location.pathname}${remainingQuery ? `?${remainingQuery}` : ''}${remainingFragment ? `#${remainingFragment}` : ''}`,
    );
    return token;
  }

  function initialize(win) {
    const form = win.document.querySelector('#form');
    const status = win.document.querySelector('#status');
    const apiInput = win.document.querySelector('#api');
    const apiLabel = win.document.querySelector('#api-label');
    const token = takeToken(win);

    if (!token) {
      status.textContent = 'This invitation link is incomplete. Ask your administrator to send a new invitation.';
      form.remove();
      return;
    }

    const configured = win.ECS_CONFIG && win.ECS_CONFIG.apiBaseUrl;
    if (configured) {
      try {
        apiInput.value = apiOrigin(configured, win.location.href);
        apiLabel.hidden = true;
      } catch (error) {
        status.textContent = `Activation is unavailable: ${error.message}`;
        form.remove();
        return;
      }
    } else {
      const page = new URL(win.location.href);
      if (page.protocol !== 'http:' || !['localhost', '127.0.0.1', '[::1]', '::1'].includes(page.hostname)) {
        status.textContent = 'Activation is unavailable because the API service is not configured.';
        form.remove();
        return;
      }
    }

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const password = win.document.querySelector('#password').value;
      if (password !== win.document.querySelector('#confirm').value) {
        status.textContent = 'Passwords do not match.';
        return;
      }
      try {
        const origin = apiOrigin(apiInput.value, win.location.href);
        const response = await win.fetch(`${origin}/api/v1/auth/accept-invitation`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token, password }),
          redirect: 'error',
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'Activation failed.');
        status.textContent = 'Account activated. You can now sign in through the mobile app.';
        form.remove();
      } catch (error) {
        status.textContent = error.message || 'Activation failed.';
      }
    });
  }

  return { apiOrigin, initialize, takeToken };
});
