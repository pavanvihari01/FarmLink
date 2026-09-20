/**
 * What Checkout sends, and what it snapshots.
 *
 * The coordinate snapshot is the contract between the buyer's saved address and
 * the farmer's delivery route. An address with a pin must carry its latitude
 * and longitude onto the order; an address without one must not invent them,
 * and the order is expected to land in the farmer's unroutable bucket instead.
 *
 * Nothing on the backend tests this. The payload is assembled in the browser
 * and the API accepts it either way.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.mock('../src/lib/api', async () => ({ api: (await import('./apiMock')).api }));

import { api, resetApiMock } from './apiMock';
import { renderWithProviders } from './renderWithProviders';
import Checkout from '../src/pages/Checkout';

const pinnedAddress = {
  id: 1,
  label: 'Home',
  line1: '12 Market Road',
  line2: null,
  city: 'Pune',
  state: 'Maharashtra',
  pincode: '411001',
  phone: null,
  latitude: 18.5204,
  longitude: 73.8567,
  is_default: true,
};

const unpinnedAddress = {
  ...pinnedAddress,
  id: 2,
  label: 'Work',
  latitude: null,
  longitude: null,
  is_default: false,
};

/** Seed the cart the way the app does, through localStorage. */
function seedCart() {
  localStorage.setItem(
    'farmlink.cart',
    JSON.stringify([
      {
        listing_id: 7,
        title: 'Tomato',
        price_per_unit: 20,
        unit: 'kg',
        image_url: '/x.jpg',
        farmer_name: 'Femi Farmer',
        available_quantity: 10,
        quantity: 2,
      },
    ]),
  );
}

/** The payload of the single checkout call, or undefined if it never fired. */
function lastPayload() {
  return api.checkout.mock.calls[0]?.[0] as Record<string, unknown> | undefined;
}

beforeEach(() => {
  resetApiMock();
  api.checkout.mockResolvedValue({ created: [], failed: [], delivery_method: 'delivery' });
});

describe('Checkout payload', () => {
  it('snapshots the pin from the chosen address', async () => {
    seedCart();
    api.addresses.mockResolvedValue([pinnedAddress]);
    renderWithProviders(<Checkout />);

    await userEvent.click(await screen.findByRole('button', { name: /place order/i }));

    await waitFor(() => expect(api.checkout).toHaveBeenCalledTimes(1));
    const payload = lastPayload()!;
    expect(payload.delivery_method).toBe('delivery');
    expect(payload.delivery_address).toBe('12 Market Road, Pune, Maharashtra, 411001');
    expect(payload.delivery_latitude).toBe(18.5204);
    expect(payload.delivery_longitude).toBe(73.8567);
  });

  it('sends no coordinates when the address has no pin', async () => {
    seedCart();
    api.addresses.mockResolvedValue([unpinnedAddress]);
    renderWithProviders(<Checkout />);

    await userEvent.click(await screen.findByRole('button', { name: /place order/i }));

    await waitFor(() => expect(api.checkout).toHaveBeenCalledTimes(1));
    const payload = lastPayload()!;
    expect(payload.delivery_address).toBe('12 Market Road, Pune, Maharashtra, 411001');
    // Absent rather than null — the order should fall into unroutable on the
    // backend, not carry a fabricated position.
    expect(payload.delivery_latitude).toBeUndefined();
    expect(payload.delivery_longitude).toBeUndefined();
  });

  it('sends the cart lines as listing ids and quantities', async () => {
    seedCart();
    api.addresses.mockResolvedValue([pinnedAddress]);
    renderWithProviders(<Checkout />);

    await userEvent.click(await screen.findByRole('button', { name: /place order/i }));

    await waitFor(() => expect(api.checkout).toHaveBeenCalledTimes(1));
    expect(lastPayload()!.items).toEqual([{ listing_id: 7, quantity: 2 }]);
  });

  it('omits the address entirely for pickup', async () => {
    seedCart();
    api.addresses.mockResolvedValue([pinnedAddress]);
    renderWithProviders(<Checkout />);

    await userEvent.click(await screen.findByRole('radio', { name: /pickup/i }));
    await userEvent.click(screen.getByRole('button', { name: /place order/i }));

    await waitFor(() => expect(api.checkout).toHaveBeenCalledTimes(1));
    const payload = lastPayload()!;
    expect(payload.delivery_method).toBe('pickup');
    expect(payload.delivery_address).toBeUndefined();
    expect(payload.delivery_latitude).toBeUndefined();
  });

  it('will not place a delivery with no address chosen', async () => {
    seedCart();
    api.addresses.mockResolvedValue([]);
    renderWithProviders(<Checkout />);

    await userEvent.click(await screen.findByRole('button', { name: /place order/i }));

    expect(api.checkout).not.toHaveBeenCalled();
    expect(await screen.findByText(/choose a delivery address/i)).toBeInTheDocument();
  });

  it('shows an empty cart rather than a form when there is nothing to buy', async () => {
    api.addresses.mockResolvedValue([pinnedAddress]);
    renderWithProviders(<Checkout />);

    expect(await screen.findByText(/your cart is empty/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /place order/i })).not.toBeInTheDocument();
  });
});
