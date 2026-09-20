import { useEffect, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import type {
  Address, Category, Farmer, PaymentMethod, Subscription, User,
} from '../types';

const FREQUENCIES: { value: 7 | 14 | 30; label: string }[] = [
  { value: 7, label: 'Every week' },
  { value: 14, label: 'Every fortnight' },
  { value: 30, label: 'Every month' },
];

const UNITS = ['kg', 'g', 'dozen', 'piece', 'bunch', 'litre'];

function frequencyLabel(days: number) {
  return FREQUENCIES.find((f) => f.value === days)?.label ?? `Every ${days} days`;
}

function shortDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
}

/** A saved address carries a pin only if the buyer dropped one in the picker. */
function hasPin(a: Address): a is Address & { latitude: number; longitude: number } {
  return typeof a.latitude === 'number' && typeof a.longitude === 'number';
}

export default function Subscriptions({ user }: { user: User }) {
  const isBuyer = user.role === 'buyer';
  const isAdmin = user.role === 'admin';

  const [subs, setSubs] = useState<Subscription[]>([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);

  const [farmers, setFarmers] = useState<Farmer[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [addresses, setAddresses] = useState<Address[]>([]);
  const [methods, setMethods] = useState<PaymentMethod[]>([]);

  const [farmerId, setFarmerId] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [quantity, setQuantity] = useState('5');
  const [unit, setUnit] = useState('kg');
  const [frequency, setFrequency] = useState<7 | 14 | 30>(7);
  const [addressId, setAddressId] = useState('');
  const [methodId, setMethodId] = useState('');
  const [creating, setCreating] = useState(false);

  const load = () => {
    setError('');
    api
      .subscriptions()
      .then(setSubs)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Unable to load subscriptions'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    // Cycle generation is a write, so it is its own POST rather than a
    // side effect of the GET above. Doing it first means the list that follows
    // already includes anything that just came due.
    api
      .generateDueSubscriptions()
      .then((r) => {
        if (r.generated > 0 || r.skipped > 0) {
          setNotice(`${r.generated} box${r.generated === 1 ? '' : 'es'} ordered, ${r.skipped} skipped.`);
        }
      })
      .catch(() => undefined)
      .finally(load);
  }, []);

  useEffect(() => {
    if (!isBuyer) return;
    api.farmers().then(setFarmers).catch(() => undefined);
    api.categories().then(setCategories).catch(() => undefined);
    api.addresses().then((rows) => {
      setAddresses(rows);
      // Only a pinned address can be delivered to, and every subscription is a
      // delivery. Auto-select a usable one rather than the default, which may
      // be unpinned.
      const usable = rows.filter(hasPin);
      setAddressId(String(usable.find((a) => a.is_default)?.id ?? usable[0]?.id ?? ''));
    }).catch(() => undefined);
    api.paymentMethods().then((rows) => {
      setMethods(rows);
      setMethodId(String(rows.find((p) => p.is_default)?.id ?? rows[0]?.id ?? ''));
    }).catch(() => undefined);
  }, [isBuyer]);

  const create = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    setNotice('');

    const qty = Number(quantity);
    if (!farmerId) return setError('Choose a farmer.');
    if (!categoryId) return setError('Choose a category.');
    if (!Number.isFinite(qty) || qty <= 0) return setError('Quantity must be greater than zero.');

    const address = addresses.find((a) => String(a.id) === addressId);
    if (!address) return setError('Choose a delivery address. Add one on your profile first.');
    if (!hasPin(address)) {
      return setError('That address has no map pin, so it cannot be delivered to. Add a pin in your profile first.');
    }

    const method = methods.find((m) => String(m.id) === methodId);

    setCreating(true);
    try {
      await api.createSubscription({
        farmer_id: Number(farmerId),
        category_id: Number(categoryId),
        quantity: qty,
        unit,
        frequency_days: frequency,
        delivery_address: [address.line1, address.line2, address.city, address.state, address.pincode]
          .filter(Boolean)
          .join(', '),
        // Every cycle is delivered, so the pin goes with the subscription.
        // Without it the generated orders could never be routed or completed.
        delivery_latitude: address.latitude,
        delivery_longitude: address.longitude,
        payment_label: method?.label,
      });
      setNotice(`Subscription started. First box in ${frequency} days.`);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'That subscription could not be created');
    } finally {
      setCreating(false);
    }
  };

  const cancel = async (id: number) => {
    setBusyId(id);
    setError('');
    setNotice('');
    try {
      await api.adminCancelSubscription(id);
      load();
      setNotice('Subscription cancelled. Cycles already ordered are unaffected.');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'That subscription could not be cancelled');
    } finally {
      setBusyId(null);
    }
  };

  const chosenFarmer = farmers.find((f) => String(f.id) === farmerId);
  const chosenCategory = categories.find((c) => String(c.id) === categoryId);
  const usableAddresses = addresses.filter(hasPin);

  /** A subscription created before pins were required cannot be delivered to. */
  const isStranded = (s: Subscription) =>
    typeof s.delivery_latitude !== 'number' || typeof s.delivery_longitude !== 'number';

  return (
    <main className="page">
      <div className="page-intro">
        <span className="eyebrow">Subscriptions</span>
        <h1>{isBuyer ? 'Your standing orders' : 'Boxes coming to you'}</h1>
        <p>
          {isBuyer
            ? 'Pick a farmer and a category. Each cycle, their freshest matching produce is ordered for you.'
            : 'Buyers who have set up a recurring box with you. Cycles generate when either of you opens this page.'}
        </p>
      </div>

      {error && <p className="error">{error}</p>}
      {notice && <p className="result-banner">{notice}</p>}

      {isBuyer && (
        <section className="section" style={{ padding: 0, marginBottom: 40 }}>
          <div className="section-heading">
            <div>
              <span className="eyebrow">New</span>
              <h2>Start a subscription</h2>
            </div>
          </div>

          <form className="auth" style={{ margin: 0, padding: 0, maxWidth: 560 }} onSubmit={create}>
            <label>
              Farmer
              <select value={farmerId} onChange={(e) => setFarmerId(e.target.value)} required>
                <option value="">Choose a farmer</option>
                {farmers.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name}
                    {f.location ? ` · ${f.location}` : ''}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Category
              <select value={categoryId} onChange={(e) => setCategoryId(e.target.value)} required>
                <option value="">Choose a category</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>

            {chosenFarmer && chosenCategory && (
              <p className="muted" style={{ margin: 0 }}>
                Each cycle, {chosenFarmer.name}&rsquo;s freshest {chosenCategory.name} with the longest
                remaining life is picked. If they have none that week, the cycle is skipped and you are told
                why.
              </p>
            )}

            <label>
              Quantity each cycle
              <input
                type="number"
                min="0.1"
                step="0.1"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                required
              />
            </label>

            <label>
              Unit
              <select value={unit} onChange={(e) => setUnit(e.target.value)}>
                {UNITS.map((u) => (
                  <option key={u} value={u}>
                    {u}
                  </option>
                ))}
              </select>
            </label>

            <label>
              How often
              <select value={frequency} onChange={(e) => setFrequency(Number(e.target.value) as 7 | 14 | 30)}>
                {FREQUENCIES.map((f) => (
                  <option key={f.value} value={f.value}>
                    {f.label}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Deliver to
              {addresses.length === 0 ? (
                <span className="muted">
                  No saved address. <Link to="/profile">Add one first.</Link>
                </span>
              ) : usableAddresses.length === 0 ? (
                <span className="muted">
                  None of your saved addresses has a map pin, and every box is delivered. Add a pin in your{' '}
                  <Link to="/profile">profile</Link> first.
                </span>
              ) : (
                <select value={addressId} onChange={(e) => setAddressId(e.target.value)} required>
                  {usableAddresses.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.label} · {[a.line1, a.city].filter(Boolean).join(', ')}
                    </option>
                  ))}
                </select>
              )}
            </label>

            <label>
              Payment method
              {methods.length === 0 ? (
                <span className="muted">
                  No saved method. You can still subscribe — it will be recorded as unpaid.
                </span>
              ) : (
                <select value={methodId} onChange={(e) => setMethodId(e.target.value)}>
                  <option value="">No preference</option>
                  {methods.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.label}
                      {m.last4 ? ` ····${m.last4}` : ''}
                    </option>
                  ))}
                </select>
              )}
            </label>

            <button className="button" type="submit" disabled={creating || !usableAddresses.length}>
              {creating ? 'Starting…' : 'Start subscription'}
            </button>
          </form>
        </section>
      )}

      <section className="section" style={{ padding: 0 }}>
        <div className="section-heading">
          <div>
            <span className="eyebrow">Active and past</span>
            <h2>{subs.length} {subs.length === 1 ? 'subscription' : 'subscriptions'}</h2>
          </div>
        </div>

        {loading && <div className="empty">Loading…</div>}

        {!loading && !subs.length && (
          <div className="empty">
            {isBuyer ? 'No subscriptions yet.' : 'Nobody has set up a recurring box with you yet.'}
          </div>
        )}

        <div style={{ display: 'grid', gap: 14 }}>
          {subs.map((s) => (
            <article className="order-card" key={s.id}>
              <div className="order-head">
                <strong>
                  {s.quantity} {s.unit} of {s.category}
                </strong>
                <span className={`order-status ${s.status === 'active' ? 'accepted' : 'cancelled'}`}>
                  {s.status}
                </span>
              </div>

              <p className="muted">
                {isBuyer ? `From ${s.farmer_name}` : `For ${s.buyer_name}`} · {frequencyLabel(s.frequency_days)}
              </p>

              {s.status === 'active' ? (
                <p style={{ margin: 0 }}>
                  Next box <strong>{shortDate(s.next_cycle_at)}</strong>
                </p>
              ) : (
                <p className="muted" style={{ margin: 0 }}>
                  Cancelled {s.cancelled_at ? shortDate(s.cancelled_at) : ''}
                </p>
              )}

              <p className="muted" style={{ margin: 0 }}>
                {isStranded(s) ? 'Addressed to' : 'Delivering to'} {s.delivery_address}
                {s.payment_label ? ` · ${s.payment_label}` : ''}
              </p>

              {isStranded(s) && s.status === 'active' && (
                <p className="muted" style={{ margin: 0 }}>
                  This one has no map pin, so its cycles are being skipped rather than delivered. Set up a new
                  subscription with a pinned address to start receiving boxes again.
                </p>
              )}

              {s.recent_cycles.length > 0 && (
                <div>
                  <span className="eyebrow">Recent cycles</span>
                  <ul style={{ margin: '6px 0 0', paddingLeft: 18, fontSize: '.86rem' }}>
                    {s.recent_cycles.map((c) => (
                      <li key={c.id} className={c.status === 'skipped' ? 'muted' : undefined}>
                        {shortDate(c.scheduled_for)} —{' '}
                        {c.status === 'generated' ? (
                          <>
                            order placed{c.order_id ? ` (#${c.order_id})` : ''}
                          </>
                        ) : (
                          <>skipped: {c.reason}</>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                {isBuyer && <Link className="inline-link" to="/orders">View orders</Link>}
                {isAdmin && s.status === 'active' && (
                  <button className="text-button" onClick={() => cancel(s.id)} disabled={busyId === s.id}>
                    {busyId === s.id ? 'Working…' : 'Cancel subscription'}
                  </button>
                )}
              </div>

              {!isAdmin && s.status === 'active' && (
                <p className="muted" style={{ margin: 0 }}>
                  Subscriptions cannot be paused or cancelled from here. Contact an admin.
                </p>
              )}
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
