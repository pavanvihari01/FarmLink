/**
 * The cart's own rules.
 *
 * CartContext keeps snapshots in localStorage and reconciles them against
 * fresh listing data. The clamp to available stock and the drop-what-is-gone
 * behaviour are both load-bearing: without them a buyer can order more than
 * exists, or be charged a price the farmer changed last week.
 */
import { describe, expect, it } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { CartProvider, useCart } from '../src/context/CartContext';
import type { Listing } from '../src/types';

function wrapper({ children }: { children: ReactNode }) {
  return <CartProvider>{children}</CartProvider>;
}

const produce = {
  listing_id: 1,
  title: 'Tomato',
  price_per_unit: 20,
  unit: 'kg',
  image_url: '/x.jpg',
  farmer_name: 'Femi Farmer',
  available_quantity: 10,
};

function listing(over: Partial<Listing> = {}): Listing {
  return {
    id: 1,
    title: 'Tomato',
    description: '',
    category: 'Tomato',
    category_id: 1,
    farmer_name: 'Femi Farmer',
    farmer_id: 1,
    location: 'Pune',
    price_per_unit: 20,
    unit: 'kg',
    available_quantity: 10,
    organic: false,
    bulk_available: false,
    freshness_status: 'Fresh',
    remaining_hours: 40,
    image_url: '/x.jpg',
    verified: true,
    latitude: null,
    longitude: null,
    distance_km: null,
    ...over,
  };
}

describe('useCart', () => {
  it('adds an item and totals it', () => {
    const { result } = renderHook(() => useCart(), { wrapper });

    act(() => result.current.add(produce, 2));

    expect(result.current.items).toHaveLength(1);
    expect(result.current.total).toBe(40);
  });

  it('clamps the quantity to what is available', () => {
    const { result } = renderHook(() => useCart(), { wrapper });

    act(() => result.current.add(produce, 999));

    expect(result.current.items[0].quantity).toBe(10);
  });

  it('adds to an existing line rather than duplicating it', () => {
    const { result } = renderHook(() => useCart(), { wrapper });

    act(() => result.current.add(produce, 1));
    act(() => result.current.add(produce, 2));

    expect(result.current.items).toHaveLength(1);
    expect(result.current.items[0].quantity).toBe(3);
  });

  it('drops a line when its quantity reaches zero', () => {
    const { result } = renderHook(() => useCart(), { wrapper });

    act(() => result.current.add(produce, 2));
    act(() => result.current.setQuantity(1, 0));

    expect(result.current.items).toHaveLength(0);
  });

  it('removes a line by listing id', () => {
    const { result } = renderHook(() => useCart(), { wrapper });

    act(() => result.current.add(produce, 2));
    act(() => result.current.remove(1));

    expect(result.current.items).toHaveLength(0);
  });

  it('adopts the fresh price when reconciling', () => {
    const { result } = renderHook(() => useCart(), { wrapper });
    act(() => result.current.add(produce, 2));

    act(() => result.current.refreshFrom([listing({ price_per_unit: 35 })]));

    expect(result.current.items[0].price_per_unit).toBe(35);
    expect(result.current.total).toBe(70);
  });

  it('drops a listing that is no longer in the marketplace', () => {
    const { result } = renderHook(() => useCart(), { wrapper });
    act(() => result.current.add(produce, 2));

    let dropped: string[] = [];
    act(() => {
      dropped = result.current.refreshFrom([]);
    });

    expect(dropped).toEqual(['Tomato']);
    expect(result.current.items).toHaveLength(0);
  });

  it('pulls the quantity down to the remaining stock when reconciling', () => {
    const { result } = renderHook(() => useCart(), { wrapper });
    act(() => result.current.add(produce, 8));

    act(() => result.current.refreshFrom([listing({ available_quantity: 3 })]));

    expect(result.current.items[0].quantity).toBe(3);
  });

  it('survives a corrupt stored cart', () => {
    localStorage.setItem('farmlink.cart', 'not json at all');

    const { result } = renderHook(() => useCart(), { wrapper });

    expect(result.current.items).toEqual([]);
  });
});
