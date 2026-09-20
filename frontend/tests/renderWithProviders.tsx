/**
 * Render a page the way App.tsx does.
 *
 * App wraps every route in MemoryRouter (via the browser router in main.tsx)
 * and CartProvider. A page rendered without CartProvider throws
 * "useCart must be used inside CartProvider" — which reads like a page bug and
 * is a harness bug.
 */
import { render, type RenderResult } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { ReactElement } from 'react';
import { CartProvider } from '../src/context/CartContext';

type Options = {
  /** The URL the router starts at. */
  path?: string;
  /** Set when the page reads useParams, e.g. '/listings/:listingId'. */
  pattern?: string;
};

export function renderWithProviders(ui: ReactElement, { path = '/', pattern }: Options = {}): RenderResult {
  const routed = pattern ? (
    <Routes>
      <Route path={pattern} element={ui} />
    </Routes>
  ) : (
    ui
  );

  return render(
    <MemoryRouter initialEntries={[path]}>
      <CartProvider>{routed}</CartProvider>
    </MemoryRouter>,
  );
}
