import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import type { Listing } from '../types';

export type CartItem = {
  listing_id: number;
  title: string;
  price_per_unit: number;
  unit: string;
  image_url: string;
  farmer_name: string;
  available_quantity: number;
  quantity: number;
};

const STORAGE_KEY = 'farmlink.cart';

type CartValue = {
  items: CartItem[];
  count: number;
  total: number;
  add: (item: Omit<CartItem, 'quantity'>, quantity?: number) => void;
  setQuantity: (listingId: number, quantity: number) => void;
  remove: (listingId: number) => void;
  clear: () => void;
  /**
   * Reconcile the cart against fresh listing data. Updates prices, units, and
   * remaining stock, and drops anything that no longer exists or has expired.
   * Returns the titles of dropped items so the caller can say what happened.
   *
   * The cart stores snapshots. Without this, a price a farmer changed last week
   * still shows in the cart, and the order is charged at the new price.
   */
  refreshFrom: (listings: Listing[]) => string[];
};

const CartContext = createContext<CartValue | null>(null);

function readStored(): CartItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    // Corrupt or unreadable storage should not break the app.
    return [];
  }
}

export function CartProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<CartItem[]>(readStored);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    } catch {
      // Storage full or blocked. The in-memory cart still works for this session.
    }
  }, [items]);

  const value = useMemo<CartValue>(
    () => ({
      items,
      count: items.length,
      total: items.reduce((n, i) => n + i.quantity * i.price_per_unit, 0),
      add: (item, quantity = 1) =>
        setItems((prev) => {
          const existing = prev.find((i) => i.listing_id === item.listing_id);
          if (existing) {
            return prev.map((i) =>
              i.listing_id === item.listing_id
                ? { ...i, ...item, quantity: Math.min(i.quantity + quantity, item.available_quantity) }
                : i
            );
          }
          return [...prev, { ...item, quantity: Math.min(quantity, item.available_quantity) }];
        }),
      setQuantity: (listingId, quantity) =>
        setItems((prev) =>
          prev
            .map((i) =>
              i.listing_id === listingId
                ? { ...i, quantity: Math.max(0, Math.min(quantity, i.available_quantity)) }
                : i
            )
            .filter((i) => i.quantity > 0)
        ),
      remove: (listingId) => setItems((prev) => prev.filter((i) => i.listing_id !== listingId)),
      clear: () => setItems([]),
      refreshFrom: (listings) => {
        const byId = new Map(listings.map((l) => [l.id, l]));
        const dropped: string[] = [];
        const next: CartItem[] = [];
        for (const i of items) {
          const fresh = byId.get(i.listing_id);
          if (!fresh) {
            // Gone from the marketplace — expired, removed, or suspended.
            dropped.push(i.title);
            continue;
          }
          next.push({
            listing_id: i.listing_id,
            title: fresh.title,
            price_per_unit: fresh.price_per_unit,
            unit: fresh.unit,
            image_url: fresh.image_url,
            farmer_name: fresh.farmer_name,
            available_quantity: fresh.available_quantity,
            quantity: Math.max(1, Math.min(i.quantity, fresh.available_quantity)),
          });
        }
        setItems(next);
        return dropped;
      },
    }),
    [items]
  );

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): CartValue {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error('useCart must be used inside CartProvider');
  return ctx;
}
