import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Trash2 } from 'lucide-react';
import { api } from '../lib/api';
import { useCart } from '../context/CartContext';
import type { User } from '../types';

export default function Cart({ user }: { user: User | null }) {
  const { items, total, setQuantity, remove, clear, refreshFrom } = useCart();
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  // The cart stores snapshots taken when items were added. Without this the
  // price a farmer changed last week still shows, and the order is charged at
  // the new price — a silent mismatch between what the buyer saw and what they
  // paid. One request, matched locally.
  useEffect(() => {
    if (!items.length) return;
    let cancelled = false;
    api
      .listings({ page_size: 48 })
      .then((page) => {
        if (cancelled) return;
        const dropped = refreshFrom(page.items);
        if (dropped.length) {
          setNotice(
            `${dropped.join(', ')} ${dropped.length === 1 ? 'is' : 'are'} no longer available and ${
              dropped.length === 1 ? 'was' : 'were'
            } removed from your cart.`,
          );
        }
      })
      .catch(() => setError('Could not check current prices. The totals below may be out of date.'))
      .finally(() => undefined);
    return () => {
      cancelled = true;
    };
    // Runs once on mount. Deliberately not keyed on `items` — refreshFrom
    // replaces them, which would loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!items.length) {
    return (
      <main className="page">
        <div className="page-intro">
          <span className="eyebrow">Your cart</span>
          <h1>Nothing here yet</h1>
          <p>Browse the marketplace and add produce to get started.</p>
        </div>
        <Link to="/marketplace" className="button">
          Go to marketplace
        </Link>
      </main>
    );
  }

  return (
    <main className="page">
      <div className="page-intro">
        <span className="eyebrow">Your cart</span>
        <h1>{items.length} {items.length === 1 ? 'item' : 'items'}</h1>
        <p>Adjust quantities, then check out in one go.</p>
      </div>

      {error && <p className="error">{error}</p>}
      {notice && <p className="result-banner">{notice}</p>}

      <div style={{ display: 'grid', gap: 14 }}>
        {items.map((i) => (
          <div className="cart-row" key={i.listing_id}>
            <img src={i.image_url} alt={i.title} />
            <div>
              <h3>
                <Link to={`/listings/${i.listing_id}`}>{i.title}</Link>
              </h3>
              <p className="muted">{i.farmer_name}</p>
            </div>
            <input
              className="qty-input"
              type="number"
              min={1}
              max={i.available_quantity}
              value={i.quantity}
              onChange={(e) => setQuantity(i.listing_id, Number(e.target.value))}
              aria-label={`Quantity for ${i.title}`}
            />
            <strong>Rs {(i.quantity * i.price_per_unit).toFixed(2)}</strong>
            <button className="text-button" onClick={() => remove(i.listing_id)} aria-label={`Remove ${i.title}`}>
              <Trash2 size={18} />
            </button>
          </div>
        ))}
      </div>

      <div className="cart-summary" style={{ marginTop: 24 }}>
        <div className="row">
          <span>Items</span>
          <span>{items.length}</span>
        </div>
        <div className="row total">
          <span>Total</span>
          <span>Rs {total.toFixed(2)}</span>
        </div>
        {user ? (
          <Link className="button" to="/checkout">
            Proceed to checkout
          </Link>
        ) : (
          <>
            <p className="muted">Sign in as a buyer to check out. Your cart is saved on this device.</p>
            <Link className="button" to="/login">
              Sign in to continue
            </Link>
          </>
        )}
        <button className="text-button" onClick={clear}>
          Empty cart
        </button>
      </div>
    </main>
  );
}
