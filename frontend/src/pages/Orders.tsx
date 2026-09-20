import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import DeliveryMiniMap from '../components/DeliveryMiniMap';
import type { DeliveryStatus, Order, OrderStatus, User } from '../types';

const TABS: { key: string; label: string; match: (s: OrderStatus) => boolean }[] = [
  { key: 'all', label: 'All', match: () => true },
  { key: 'open', label: 'Open', match: (s) => s === 'requested' || s === 'accepted' },
  { key: 'completed', label: 'Completed', match: (s) => s === 'completed' },
  { key: 'cancelled', label: 'Cancelled', match: (s) => s === 'rejected' || s === 'cancelled' },
];

const FARMER_ACTIONS: Partial<Record<OrderStatus, { label: string; next: OrderStatus; primary: boolean }[]>> = {
  requested: [
    { label: 'Accept', next: 'accepted', primary: true },
    { label: 'Reject', next: 'rejected', primary: false },
  ],
  accepted: [{ label: 'Mark completed', next: 'completed', primary: true }],
};

// Admin sees the same transitions as a farmer, but is not limited by ownership.
const ADMIN_ACTIONS: Record<OrderStatus, { label: string; next: OrderStatus; primary: boolean }[]> = {
  requested: [
    { label: 'Accept', next: 'accepted', primary: true },
    { label: 'Reject', next: 'rejected', primary: false },
    { label: 'Cancel', next: 'cancelled', primary: false },
  ],
  accepted: [
    { label: 'Mark completed', next: 'completed', primary: true },
    { label: 'Cancel', next: 'cancelled', primary: false },
  ],
  rejected: [],
  cancelled: [],
  completed: [],
};

const REOPENABLE: OrderStatus[] = ['rejected', 'cancelled'];

const DELIVERY_LABEL: Record<DeliveryStatus, string> = {
  pending: 'Delivery pending',
  out_for_delivery: 'Out for delivery',
  delivered: 'Delivered',
  failed: 'Delivery failed',
};

export default function Orders({ user }: { user: User }) {
  const [orders, setOrders] = useState<Order[]>([]);
  const [tab, setTab] = useState('all');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busyId, setBusyId] = useState<number | null>(null);

  const isBuyer = user.role === 'buyer';
  const isFarmer = user.role === 'farmer';
  const isAdmin = user.role === 'admin';

  const load = () =>
    (isAdmin ? api.adminOrders() : api.orders())
      .then(setOrders)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Unable to load orders'));

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const visible = useMemo(() => {
    const t = TABS.find((x) => x.key === tab) ?? TABS[0];
    return orders.filter((o) => t.match(o.status));
  }, [orders, tab]);

  const run = async (id: number, fn: () => Promise<unknown>, successMessage?: string) => {
    setBusyId(id);
    setError('');
    setNotice('');
    try {
      await fn();
      await load();
      if (successMessage) setNotice(successMessage);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'That action could not be completed');
    } finally {
      setBusyId(null);
    }
  };

  const cancel = (id: number) => run(id, () => api.cancelOrder(id), 'Order cancelled.');

  const advance = (id: number, next: OrderStatus) =>
    run(id, () => api.updateOrderStatus(id, next), `Order marked ${next}.`);

  const advanceDelivery = (id: number, next: DeliveryStatus) =>
    run(id, () => api.updateDeliveryStatus(id, next), `Delivery marked ${DELIVERY_LABEL[next].toLowerCase()}.`);

  const reopen = async (id: number) => {
    setBusyId(id);
    setError('');
    setNotice('');
    try {
      const r = await api.reopenOrder(id);
      await load();
      setNotice(
        r.capped
          ? `Order reopened at ${r.quantity} units — only that much stock was left. Total is now Rs ${r.total_amount.toFixed(2)}.`
          : `Order reopened at the original quantity of ${r.quantity}.`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : 'That order could not be reopened');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <main className="page">
      <div className="page-intro">
        <span className="eyebrow">Orders</span>
        <h1>{isBuyer ? 'What you have ordered' : isAdmin ? 'Every order' : 'Orders you have received'}</h1>
        <p>
          {isAdmin
            ? 'Newest first. An admin can move any order to any legal status.'
            : isFarmer
              ? 'Accept or reject new requests, mark accepted orders complete, and reopen ones you declined.'
              : 'Newest first. Cancel an order while it is still open.'}
        </p>
      </div>

      {error && <p className="error">{error}</p>}
      {notice && <p className="result-banner">{notice}</p>}

      <div className="tabs">
        {TABS.map((t) => (
          <button key={t.key} className={tab === t.key ? 'active' : ''} onClick={() => setTab(t.key)}>
            {t.label}
          </button>
        ))}
      </div>

      {!visible.length && (
        <div className="empty">
          {orders.length === 0
            ? isFarmer
              ? 'No one has ordered from you yet.'
              : isAdmin
                ? 'No orders exist yet.'
                : 'You have not placed any orders yet.'
            : 'No orders in this tab.'}
        </div>
      )}

      <div style={{ display: 'grid', gap: 14 }}>
        {visible.map((o) => {
          const canCancel = isBuyer && (o.status === 'requested' || o.status === 'accepted');
          const farmerActions = isFarmer ? FARMER_ACTIONS[o.status] ?? [] : [];
          const adminActions = isAdmin ? ADMIN_ACTIONS[o.status] ?? [] : [];
          const actions = isAdmin ? adminActions : farmerActions;
          const canReopen = (isFarmer || isAdmin) && REOPENABLE.includes(o.status);
          const busy = busyId === o.id;
          const isDelivery = o.delivery_method === 'delivery';
          const canTouchDelivery = (isFarmer || isAdmin) && o.status === 'accepted' && isDelivery;
          const showMap =
            isBuyer &&
            isDelivery &&
            o.delivery_latitude !== null &&
            o.delivery_latitude !== undefined &&
            o.delivery_longitude !== null &&
            o.delivery_longitude !== undefined;

          return (
            <article className="order-card" key={o.id}>
              <div className="order-head">
                <strong>{o.listing_title}</strong>
                <span className={`order-status ${o.status}`}>{o.status}</span>
              </div>

              {isAdmin ? (
                <p className="muted">
                  Buyer: {o.counterparty} · Farmer: {o.farmer_name} · Order #{o.id}
                </p>
              ) : (
                <p className="muted">
                  {isBuyer ? `From ${o.counterparty}` : `Buyer: ${o.counterparty}`} · Order #{o.id}
                </p>
              )}

              <p style={{ margin: 0 }}>
                {o.quantity} kg · <strong>Rs {o.total_amount.toFixed(2)}</strong>
              </p>

              {isDelivery ? (
                <>
                  {o.delivery_address && <p className="muted">Deliver to {o.delivery_address}</p>}
                  {o.delivery_status && (
                    <p style={{ margin: 0 }}>
                      <span className="muted">{DELIVERY_LABEL[o.delivery_status]}</span>
                    </p>
                  )}
                  {o.delivery_note && <p className="muted">{o.delivery_note}</p>}
                  {!showMap && (o.delivery_latitude === null || o.delivery_latitude === undefined) && (
                    <p className="muted" style={{ margin: 0 }}>
                      Address not pinned
                    </p>
                  )}
                  {showMap && (
                    <DeliveryMiniMap lat={o.delivery_latitude as number} lng={o.delivery_longitude as number} />
                  )}
                </>
              ) : (
                <p className="muted" style={{ margin: 0 }}>
                  Pickup from the farm
                </p>
              )}

              {o.payment_label && <p className="muted">Payment: {o.payment_label}</p>}

              <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                <Link className="inline-link" to={`/listings/${o.listing_id}`}>
                  View listing
                </Link>
                {isBuyer && <Link className="text-button" to={`/report/${o.listing_id}`}>Report an issue</Link>}

                {canCancel && (
                  <button className="text-button" onClick={() => cancel(o.id)} disabled={busy}>
                    {busy ? 'Working…' : 'Cancel order'}
                  </button>
                )}

                {actions.map((a) =>
                  a.primary ? (
                    <button
                      key={a.label}
                      className="button small"
                      onClick={() => advance(o.id, a.next)}
                      disabled={busy}
                    >
                      {busy ? 'Working…' : a.label}
                    </button>
                  ) : (
                    <button
                      key={a.label}
                      className="text-button"
                      onClick={() => advance(o.id, a.next)}
                      disabled={busy}
                    >
                      {busy ? 'Working…' : a.label}
                    </button>
                  )
                )}

                {canReopen && (
                  <button className="button small" onClick={() => reopen(o.id)} disabled={busy}>
                    {busy ? 'Working…' : 'Reopen'}
                  </button>
                )}

                {canTouchDelivery && o.delivery_status === 'pending' && (
                  <button className="button small" onClick={() => advanceDelivery(o.id, 'out_for_delivery')} disabled={busy}>
                    {busy ? 'Working…' : 'Start delivery'}
                  </button>
                )}
                {canTouchDelivery && o.delivery_status === 'out_for_delivery' && (
                  <button className="button small" onClick={() => advanceDelivery(o.id, 'delivered')} disabled={busy}>
                    {busy ? 'Working…' : 'Mark delivered'}
                  </button>
                )}
              </div>
            </article>
          );
        })}
      </div>
    </main>
  );
}
