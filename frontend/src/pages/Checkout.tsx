import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, type CheckoutPayload } from '../lib/api';
import { useCart } from '../context/CartContext';
import type { Address, CheckoutResult, DeliveryMethod, PaymentMethod } from '../types';

/** One-line form of a saved address, the same shape the backend stores on the order. */
function addressLine(a: Address): string {
  return [a.line1, a.line2, a.city, a.state, a.pincode].filter(Boolean).join(', ');
}

/** A saved address carries a pin only if the buyer dropped one in the location picker. */
function hasPin(a: Address | null): a is Address & { latitude: number; longitude: number } {
  return a !== null && typeof a.latitude === 'number' && typeof a.longitude === 'number';
}

export default function Checkout() {
  const { items, total, remove, clear } = useCart();
  const [addresses, setAddresses] = useState<Address[]>([]);
  const [methods, setMethods] = useState<PaymentMethod[]>([]);
  const [method, setMethod] = useState<DeliveryMethod>('delivery');
  const [addressId, setAddressId] = useState<number | null>(null);
  const [methodId, setMethodId] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [placing, setPlacing] = useState(false);
  const [result, setResult] = useState<CheckoutResult | null>(null);

  useEffect(() => {
    api.addresses().then((rows) => {
      setAddresses(rows);
      setAddressId(rows.find((a) => a.is_default)?.id ?? rows[0]?.id ?? null);
    }).catch(() => setError('Unable to load your addresses'));
    api.paymentMethods().then((rows) => {
      setMethods(rows);
      setMethodId(rows.find((m) => m.is_default)?.id ?? rows[0]?.id ?? null);
    }).catch(() => setError('Unable to load your payment methods'));
  }, []);

  const selectedAddress = addresses.find((a) => a.id === addressId) ?? null;
  const selectedMethod = methods.find((m) => m.id === methodId) ?? null;

  const placeOrder = async () => {
    setError('');
    if (method === 'delivery' && !selectedAddress) {
      setError('Choose a delivery address, or switch to pickup.');
      return;
    }
    if (method === 'delivery' && selectedAddress && !hasPin(selectedAddress)) {
      setError('Please pin your delivery location on the map.');
      return;
    }
    setPlacing(true);
    try {
      const payload: CheckoutPayload = {
        items: items.map((i) => ({ listing_id: i.listing_id, quantity: i.quantity })),
        delivery_method: method,
        payment_mode: 'demo',
      };
      if (method === 'delivery' && selectedAddress) {
        payload.delivery_address = addressLine(selectedAddress);
        // The guard above already rejected an unpinned address, so the pin is
        // present. hasPin narrows the type for the compiler.
        if (hasPin(selectedAddress)) {
          payload.delivery_latitude = selectedAddress.latitude;
          payload.delivery_longitude = selectedAddress.longitude;
        }
      }
      if (selectedMethod) payload.payment_label = selectedMethod.label;

      const out = await api.checkout(payload);
      setResult(out);
      // Only the lines that actually became orders leave the cart. A rejected
      // item stays put so the buyer can fix it and try again.
      for (const c of out.created) remove(c.listing_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'The order could not be placed');
    } finally {
      setPlacing(false);
    }
  };

  // ---------------------------------------------------------------------
  // After placing
  // ---------------------------------------------------------------------
  if (result) {
    return (
      <main className="page">
        <div className="page-intro">
          <span className="eyebrow">Checkout</span>
          <h1>Order placed</h1>
          <p>The farmer has been notified and will accept or decline each line.</p>
        </div>

        {result.created.length > 0 && (
          <div style={{ display: 'grid', gap: 14 }}>
            {result.created.map((c) => (
              <article className="order-card" key={c.order_id}>
                <div className="order-head">
                  <strong>{c.title}</strong>
                  <span className="order-status requested">Requested</span>
                </div>
                <p className="muted" style={{ margin: 0 }}>
                  Order #{c.order_id} · {c.quantity} · Rs {c.total_amount.toFixed(2)}
                </p>
              </article>
            ))}
          </div>
        )}

        {result.failed.length > 0 && (
          <>
            <h2 style={{ marginTop: 28 }}>Could not be ordered</h2>
            <div style={{ display: 'grid', gap: 14 }}>
              {result.failed.map((f) => (
                <article className="order-card" key={f.listing_id}>
                  <p style={{ margin: 0 }}>{f.reason}</p>
                </article>
              ))}
            </div>
          </>
        )}

        <div className="cart-summary" style={{ marginTop: 24 }}>
          <Link className="button" to="/orders">
            View your orders
          </Link>
          <Link className="text-button" to="/marketplace">
            Keep shopping
          </Link>
        </div>
      </main>
    );
  }

  // ---------------------------------------------------------------------
  // Nothing to check out
  // ---------------------------------------------------------------------
  if (!items.length) {
    return (
      <main className="page">
        <div className="page-intro">
          <span className="eyebrow">Checkout</span>
          <h1>Your cart is empty</h1>
          <p>Add produce from the marketplace before checking out.</p>
        </div>
        <Link className="button" to="/marketplace">
          Go to marketplace
        </Link>
      </main>
    );
  }

  // ---------------------------------------------------------------------
  // The form
  // ---------------------------------------------------------------------
  return (
    <main className="page">
      <div className="page-intro">
        <span className="eyebrow">Checkout</span>
        <h1>Confirm your order</h1>
        <p>Each line becomes its own order, so a farmer can accept or decline independently.</p>
      </div>

      {error && <p className="error">{error}</p>}

      <h2>Items</h2>
      <div style={{ display: 'grid', gap: 14 }}>
        {items.map((i) => (
          <div className="cart-row" key={i.listing_id}>
            <img src={i.image_url} alt={i.title} />
            <div>
              <h3>{i.title}</h3>
              <p className="muted">{i.farmer_name}</p>
            </div>
            <span className="muted">
              {i.quantity} {i.unit}
            </span>
            <strong>Rs {(i.quantity * i.price_per_unit).toFixed(2)}</strong>
            <button
              className="text-button"
              onClick={() => remove(i.listing_id)}
              aria-label={`Remove ${i.title}`}
            >
              Remove
            </button>
          </div>
        ))}
      </div>

      <h2 style={{ marginTop: 28 }}>Delivery</h2>
      <div className="v-control-group" style={{ display: 'flex', gap: 18 }}>
        <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input
            type="radio"
            name="delivery-method"
            checked={method === 'delivery'}
            onChange={() => setMethod('delivery')}
          />
          Delivery
        </label>
        <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input
            type="radio"
            name="delivery-method"
            checked={method === 'pickup'}
            onChange={() => setMethod('pickup')}
          />
          Pickup from the farm
        </label>
      </div>

      {method === 'delivery' && (
        <div style={{ marginTop: 16 }}>
          {addresses.length === 0 ? (
            <p className="muted">
              You have no saved addresses.{' '}
              <Link to="/profile">Add one in your profile</Link> to have this delivered.
            </p>
          ) : (
            <div style={{ display: 'grid', gap: 12 }}>
              {addresses.map((a) => (
                <label
                  className="order-card"
                  key={a.id}
                  style={{ display: 'flex', gap: 12, alignItems: 'flex-start', cursor: 'pointer' }}
                >
                  <input
                    type="radio"
                    name="address"
                    checked={addressId === a.id}
                    onChange={() => setAddressId(a.id)}
                    style={{ marginTop: 4 }}
                  />
                  <span>
                    <strong>{a.label}</strong>
                    {a.is_default && <span className="muted"> · default</span>}
                    <br />
                    <span className="muted">{addressLine(a)}</span>
                    {!hasPin(a) && (
                      <>
                        <br />
                        <span className="muted">
                          No map pin — this delivery will not appear on the route map.
                        </span>
                      </>
                    )}
                  </span>
                </label>
              ))}
            </div>
          )}
        </div>
      )}

      <h2 style={{ marginTop: 28 }}>Payment</h2>
      {methods.length === 0 ? (
        <p className="muted">
          No saved payment methods. <Link to="/profile">Add one in your profile</Link>, or continue — this
          demo records the order without charging it.
        </p>
      ) : (
        <div style={{ display: 'grid', gap: 12 }}>
          {methods.map((m) => (
            <label
              className="order-card"
              key={m.id}
              style={{ display: 'flex', gap: 12, alignItems: 'center', cursor: 'pointer' }}
            >
              <input
                type="radio"
                name="payment"
                checked={methodId === m.id}
                onChange={() => setMethodId(m.id)}
              />
              <span>
                <strong>{m.label}</strong>
                <span className="muted"> · {m.method_type.toUpperCase()}</span>
                {m.last4 && <span className="muted"> ending {m.last4}</span>}
              </span>
            </label>
          ))}
        </div>
      )}

      <div className="cart-summary" style={{ marginTop: 24 }}>
        <div className="row">
          <span>Items</span>
          <span>{items.length}</span>
        </div>
        <div className="row total">
          <span>Total</span>
          <span>Rs {total.toFixed(2)}</span>
        </div>
        <button className="button" onClick={placeOrder} disabled={placing}>
          {placing ? 'Placing…' : 'Place order'}
        </button>
        <button className="text-button" onClick={clear} disabled={placing}>
          Empty cart
        </button>
      </div>
    </main>
  );
}
