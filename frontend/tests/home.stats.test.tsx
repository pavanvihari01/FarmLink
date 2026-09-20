/**
 * The home page shows a real count or nothing.
 *
 * It used to show "42 nearby farms" and "6h average harvest-to-order" as
 * literal strings. Neither came from the database, and the first claimed
 * proximity the visitor's location was never used to establish — an anonymous
 * visitor has no location on this page.
 *
 * The replacement is the `total` from the listings response App already
 * fetches. These tests pin that the number is real, and that nothing renders
 * before it arrives.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../src/lib/api', async () => ({ api: (await import('./apiMock')).api }));

import { api, resetApiMock } from './apiMock';
import App from '../src/App';
import Home from '../src/pages/Home';

beforeEach(() => {
  resetApiMock();
  localStorage.clear();
});

/**
 * The figure lives in a <strong> and the label in the surrounding <span>, so
 * no single element's text is "N listings ready now".
 *
 * @testing-library matches an element's own text nodes, not its descendants'
 * text — which is why findByText('1 listing ready now') finds nothing here.
 * These two queries match what is actually in the DOM.
 */
async function findCount(figure: string) {
  expect(await screen.findByText(figure)).toBeInTheDocument();
}

describe('home page count', () => {
  it('renders the total the API returned', async () => {
    api.listings.mockResolvedValue({ items: [], total: 17, page: 1, pages: 2, page_size: 4 });

    render(<MemoryRouter><App /></MemoryRouter>);

    // The number comes from the response, not from the markup.
    await findCount('17');
    expect(screen.getByText(/listings ready now/i)).toBeInTheDocument();
  });

  it('says listing rather than listings when there is one', async () => {
    api.listings.mockResolvedValue({ items: [], total: 1, page: 1, pages: 1, page_size: 4 });

    render(<MemoryRouter><App /></MemoryRouter>);

    await findCount('1');
    // Singular, and the plural label is gone. The regex is anchored to the
    // word boundary so "listings ready now" cannot satisfy it.
    expect(screen.getByText(/^listing ready now$/i)).toBeInTheDocument();
    expect(screen.queryByText(/^listings ready now$/i)).not.toBeInTheDocument();
  });

  it('shows no figure before the count arrives', () => {
    render(<MemoryRouter><Home items={[]} liveCount={null} /></MemoryRouter>);

    // Nothing rather than a zero, which would read as "the marketplace is
    // empty" during the moment before the request resolves.
    expect(screen.queryByText(/ready now/i)).not.toBeInTheDocument();
  });

  it('never renders the invented figures', () => {
    render(<MemoryRouter><Home items={[]} liveCount={5} /></MemoryRouter>);

    expect(screen.queryByText(/42/)).not.toBeInTheDocument();
    expect(screen.queryByText(/nearby farms/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/harvest-to-order/i)).not.toBeInTheDocument();
  });
});
