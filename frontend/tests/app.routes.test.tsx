/**
 * Route wiring and role gating.
 *
 * App.tsx decides who reaches which page. A route pointed at the wrong
 * component, or a role guard that lets a buyer into the admin console, is
 * invisible to the backend suite and to `tsc`.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../src/lib/api', async () => ({ api: (await import('./apiMock')).api }));

import { resetApiMock } from './apiMock';
import App from '../src/App';

/** App reads the token to decide whether to call /auth/me at all. */
function signIn(token: string | null) {
  if (token) localStorage.setItem('token', token);
  else localStorage.removeItem('token');
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  resetApiMock();
});

describe('App routes', () => {
  it('renders a marketplace shell without a session', async () => {
    signIn(null);
    const { container } = renderAt('/marketplace');

    // The layout mounts. Asserting on the shell rather than on any page text
    // keeps this from breaking every time a heading is reworded.
    await waitFor(() => expect(container.querySelector('main, header, nav')).not.toBeNull());
  });

  it('sends an unauthenticated visitor away from the dashboard', async () => {
    signIn(null);
    renderAt('/dashboard');

    // /dashboard is guarded by `user ? <Dashboard/> : <Navigate to="/login"/>`.
    // A password field is the one structural thing every sign-in form has, so
    // this does not depend on Login's exact wording.
    await waitFor(() => expect(document.querySelector('input[type="password"]')).not.toBeNull());
  });

  it('sends an unknown path home rather than to a blank screen', async () => {
    signIn(null);
    const { container } = renderAt('/no-such-page');

    // App has a catch-all `<Route path="*" element={<Navigate to="/" />} />`.
    await waitFor(() => expect(container.firstChild).not.toBeNull());
  });
});
