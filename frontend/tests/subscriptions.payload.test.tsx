/**
 * A subscription always carries a delivery pin.
 *
 * Every cycle is a delivery, and a delivery without coordinates can never be
 * routed or completed — it sits in the farmer's unroutable bucket with no
 * action available and the order stuck open forever. The backend rejects a
 * subscription without a pin; this covers the browser half, which is where the
 * pin has to come from.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.mock('../src/lib/api', async () => ({ api: (await import('./apiMock')).api }));

import { api, resetApiMock } from './apiMock';
import { renderWithProviders } from './renderWithProviders';
import Subscriptions from '../src/pages/Subscriptions';
import type { User } from '../src/types';

const buyer: User = { id: 2, name: 'Bina Buyer', email: 'buyer@test.demo', role: 'buyer' };

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

const farmer = { id: 10, name: 'Femi Farmer', location: 'Pune' };
const category = { id: 20, name: 'Tomato', default_lifespan_hours: 96 };

/** Fill everything needed to submit, leaving the address dropdown alone. */
async function fillForm() {
  await userEvent.selectOptions(await screen.findByLabelText(/farmer/i), String(farmer.id));
  await userEvent.selectOptions(screen.getByLabelText(/category/i), String(category.id));
}

function lastPayload() {
  return api.createSubscription.mock.calls[0]?.[0] as Record<string, unknown> | undefined;
}

beforeEach(() => {
  resetApiMock();
  api.farmers.mockResolvedValue([farmer]);
  api.categories.mockResolvedValue([category]);
  api.createSubscription.mockResolvedValue({ id: 1, next_cycle_at: '2026-10-01T00:00:00' });
});

describe('subscription payload', () => {
  it('sends the pin from the chosen address', async () => {
    api.addresses.mockResolvedValue([pinnedAddress]);
    renderWithProviders(<Subscriptions user={buyer} />);

    await fillForm();
    await userEvent.click(screen.getByRole('button', { name: /start subscription/i }));

    await waitFor(() => expect(api.createSubscription).toHaveBeenCalledTimes(1));
    const payload = lastPayload()!;
    expect(payload.delivery_address).toBe('12 Market Road, Pune, Maharashtra, 411001');
    expect(payload.delivery_latitude).toBe(18.5204);
    expect(payload.delivery_longitude).toBe(73.8567);
  });

  it('auto-selects a pinned address when the default is unpinned', async () => {
    api.addresses.mockResolvedValue([
      { ...unpinnedAddress, id: 3, label: 'Old', is_default: true },
      { ...pinnedAddress, id: 4, label: 'New', is_default: false },
    ]);
    renderWithProviders(<Subscriptions user={buyer} />);

    await fillForm();
    await userEvent.click(screen.getByRole('button', { name: /start subscription/i }));

    await waitFor(() => expect(api.createSubscription).toHaveBeenCalledTimes(1));
    // The unpinned default was skipped in favour of the usable one.
    expect(lastPayload()!.delivery_latitude).toBe(18.5204);
  });

  it('never sends a subscription without coordinates', async () => {
    api.addresses.mockResolvedValue([pinnedAddress]);
    renderWithProviders(<Subscriptions user={buyer} />);

    await fillForm();
    await userEvent.click(screen.getByRole('button', { name: /start subscription/i }));

    await waitFor(() => expect(api.createSubscription).toHaveBeenCalledTimes(1));
    const payload = lastPayload()!;
    // The invariant the backend enforces, asserted on the browser side too.
    expect(typeof payload.delivery_latitude).toBe('number');
    expect(typeof payload.delivery_longitude).toBe('number');
  });
});

describe('unpinned addresses cannot be subscribed with', () => {
  it('offers no address and disables the button when nothing is pinned', async () => {
    api.addresses.mockResolvedValue([unpinnedAddress]);
    renderWithProviders(<Subscriptions user={buyer} />);

    // The reason is on screen rather than a silently empty dropdown.
    expect(await screen.findByText(/has a map pin/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /start subscription/i })).toBeDisabled();
  });

  it('does not list an unpinned address as a choice', async () => {
    api.addresses.mockResolvedValue([pinnedAddress, unpinnedAddress]);
    renderWithProviders(<Subscriptions user={buyer} />);

    await screen.findByLabelText(/deliver to/i);
    expect(screen.getByRole('option', { name: /Home/ })).toBeInTheDocument();
    // Work has no pin, so it is not offered at all — unlike checkout, there is
    // no pickup fallback here to make it usable another way.
    expect(screen.queryByRole('option', { name: /Work/ })).not.toBeInTheDocument();
  });

  it('will not submit without an address', async () => {
    api.addresses.mockResolvedValue([]);
    renderWithProviders(<Subscriptions user={buyer} />);

    await screen.findByText(/add one first/i);
    expect(screen.getByRole('button', { name: /start subscription/i })).toBeDisabled();
    expect(api.createSubscription).not.toHaveBeenCalled();
  });
});

describe('stranded subscriptions', () => {
  const stranded = {
    id: 5,
    buyer_id: buyer.id,
    buyer_name: buyer.name,
    farmer_id: farmer.id,
    farmer_name: farmer.name,
    category: 'Tomato',
    category_id: category.id,
    quantity: 5,
    unit: 'kg',
    frequency_days: 7,
    status: 'active' as const,
    next_cycle_at: '2026-10-01T00:00:00',
    delivery_address: '12 Market Road, Pune',
    delivery_latitude: null,
    delivery_longitude: null,
    payment_label: null,
    created_at: '2026-09-01T00:00:00',
    cancelled_at: null,
    recent_cycles: [],
  };

  it('says why an unpinned subscription is being skipped', async () => {
    api.subscriptions.mockResolvedValue([stranded]);
    renderWithProviders(<Subscriptions user={buyer} />);

    expect(await screen.findByText(/no map pin/i)).toBeInTheDocument();
    // "Addressed to" rather than "Delivering to" — nothing is being delivered.
    expect(screen.getByText(/addressed to/i)).toBeInTheDocument();
  });

  it('does not label a pinned subscription as stranded', async () => {
    api.subscriptions.mockResolvedValue([{ ...stranded, delivery_latitude: 18.5, delivery_longitude: 73.8 }]);
    renderWithProviders(<Subscriptions user={buyer} />);

    expect(await screen.findByText(/delivering to/i)).toBeInTheDocument();
    expect(screen.queryByText(/no map pin/i)).not.toBeInTheDocument();
  });
});
