/**
 * Every page module imports and renders without throwing.
 *
 * This is the test that would have caught the two files that shipped
 * truncated — Checkout.tsx ended mid-expression and Deliveries.tsx ended
 * mid-JSX. Neither was reachable by the backend suite, and `tsc` reports only
 * the first error it hits, so both survived a green backend and a build nobody
 * had run.
 *
 * One test per page, so a failure names the file rather than pointing at a
 * shared harness.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';

vi.mock('../src/lib/api', async () => ({ api: (await import('./apiMock')).api }));

import { api, resetApiMock } from './apiMock';
import { renderWithProviders } from './renderWithProviders';

import Home from '../src/pages/Home';
import Marketplace from '../src/pages/Marketplace';
import ListingDetail from '../src/pages/ListingDetail';
import EditListing from '../src/pages/EditListing';
import HowItWorks from '../src/pages/HowItWorks';
import Cart from '../src/pages/Cart';
import ReportPage from '../src/pages/Report';
import Login from '../src/pages/Login';
import Register from '../src/pages/Register';
import Checkout from '../src/pages/Checkout';
import Orders from '../src/pages/Orders';
import Subscriptions from '../src/pages/Subscriptions';
import Deliveries from '../src/pages/Deliveries';
import Forecast from '../src/pages/Forecast';
import Profile from '../src/pages/Profile';
import CreateListing from '../src/pages/CreateListing';
import Admin from '../src/pages/Admin';
import Dashboard from '../src/pages/Dashboard';
import type { Listing, User } from '../src/types';

const buyer: User = { id: 2, name: 'Bina Buyer', email: 'buyer@test.demo', role: 'buyer' };
const farmer: User = { id: 1, name: 'Femi Farmer', email: 'farmer@test.demo', role: 'farmer' };
const admin: User = { id: 3, name: 'Ada Admin', email: 'admin@test.demo', role: 'admin' };

const noListings: Listing[] = [];

/** A page mounted, at minimum, means it produced a DOM node. */
function expectRendered(container: HTMLElement) {
  expect(container.firstChild).not.toBeNull();
}

beforeEach(() => {
  resetApiMock();
  // Deliveries calls window.prompt when a delivery is marked failed. Nothing
  // in these tests does, but a stray call would otherwise block on a real
  // dialog.
  window.prompt = vi.fn();
});

describe('every page renders', () => {
  it('Home', () => {
    expectRendered(renderWithProviders(<Home items={noListings} liveCount={null} />).container);
  });

  it('Marketplace', () => {
    expectRendered(renderWithProviders(<Marketplace />).container);
  });

  it('ListingDetail', () => {
    expectRendered(
      renderWithProviders(<ListingDetail user={buyer} />, {
        path: '/listings/1',
        pattern: '/listings/:listingId',
      }).container,
    );
  });

  it('EditListing', () => {
    expectRendered(
      renderWithProviders(<EditListing user={farmer} />, {
        path: '/listings/1/edit',
        pattern: '/listings/:listingId/edit',
      }).container,
    );
  });

  it('HowItWorks', () => {
    expectRendered(renderWithProviders(<HowItWorks />).container);
  });

  it('Cart', () => {
    expectRendered(renderWithProviders(<Cart user={buyer} />).container);
  });

  it('Cart signed out', () => {
    expectRendered(renderWithProviders(<Cart user={null} />).container);
  });

  it('Report', () => {
    expectRendered(
      renderWithProviders(<ReportPage user={buyer} />, { path: '/report/1', pattern: '/report/:listingId' })
        .container,
    );
  });

  it('Login', () => {
    expectRendered(renderWithProviders(<Login onLogin={vi.fn()} />).container);
  });

  it('Register', () => {
    expectRendered(renderWithProviders(<Register onLogin={vi.fn()} />).container);
  });

  it('Checkout', () => {
    expectRendered(renderWithProviders(<Checkout />).container);
  });

  it('Orders', () => {
    expectRendered(renderWithProviders(<Orders user={buyer} />).container);
  });

  it('Subscriptions', () => {
    expectRendered(renderWithProviders(<Subscriptions user={buyer} />).container);
  });

  it('Deliveries', () => {
    expectRendered(renderWithProviders(<Deliveries user={farmer} />).container);
  });

  it('Forecast', () => {
    expectRendered(renderWithProviders(<Forecast user={farmer} />).container);
  });

  it('Profile', () => {
    expectRendered(renderWithProviders(<Profile user={buyer} onUserUpdate={vi.fn()} />).container);
  });

  it('CreateListing', () => {
    expectRendered(renderWithProviders(<CreateListing user={farmer} />).container);
  });

  it('Admin', () => {
    expectRendered(renderWithProviders(<Admin user={admin} />).container);
  });

  it('Dashboard as buyer', () => {
    expectRendered(renderWithProviders(<Dashboard user={buyer} items={noListings} />).container);
  });

  it('Dashboard as farmer', () => {
    expectRendered(renderWithProviders(<Dashboard user={farmer} items={noListings} />).container);
  });
});

describe('pages reach the API they need', () => {
  it('Marketplace loads its categories', async () => {
    renderWithProviders(<Marketplace />);

    // Categories populate the filter, so the page is only usable once they
    // arrive. This is the call the first version of this suite forgot to mock.
    await vi.waitFor(() => expect(api.categories).toHaveBeenCalled());
  });

  it('Subscriptions asks for due cycles', async () => {
    renderWithProviders(<Subscriptions user={buyer} />);

    await vi.waitFor(() => expect(api.generateDueSubscriptions).toHaveBeenCalled());
  });

  it('Deliveries loads the route', async () => {
    renderWithProviders(<Deliveries user={farmer} />);

    await vi.waitFor(() => expect(api.deliveryRoute).toHaveBeenCalled());
    expect(await screen.findByText(/no deliveries in progress/i)).toBeInTheDocument();
  });
});
