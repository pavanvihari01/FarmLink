import { useEffect, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import type {
  AdminListing, AdminMetrics, AdminUser, Category, ListingModerationStatus,
  Order, Report, Subscription, User,
} from '../types';

const TABS = [
  { key: 'metrics', label: 'Overview' },
  { key: 'users', label: 'Users' },
  { key: 'listings', label: 'Listings' },
  { key: 'orders', label: 'Orders' },
  { key: 'categories', label: 'Categories' },
  { key: 'reports', label: 'Reports' },
  { key: 'subscriptions', label: 'Subscriptions' },
];

const STATUS_LABEL: Record<string, string> = {
  active: 'Active',
  suspended: 'Suspended',
  removed: 'Removed',
};

function shortDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
}

export default function Admin({ user }: { user: User }) {
  const [tab, setTab] = useState('metrics');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const [metrics, setMetrics] = useState<AdminMetrics | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [listings, setListings] = useState<AdminListing[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [busyId, setBusyId] = useState<number | null>(null);

  const [confirmRemove, setConfirmRemove] = useState<{ listing: AdminListing; reason: string } | null>(null);
  const [closingReport, setClosingReport] = useState<{ report: Report; note: string } | null>(null);

  const load = () => {
    setError('');
    api.adminMetrics().then(setMetrics).catch(() => setError('Unable to load metrics.'));
    api.adminUsers().then(setUsers).catch(() => setError('Unable to load users.'));
    api.adminListings().then(setListings).catch(() => setError('Unable to load listings.'));
    api.adminOrders().then(setOrders).catch(() => setError('Unable to load orders.'));
    api.categories().then(setCategories).catch(() => setError('Unable to load categories.'));
    api.allReports().then(setReports).catch(() => setError('Unable to load reports.'));
    api.adminSubscriptions().then(setSubscriptions).catch(() => setError('Unable to load subscriptions.'));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const run = async (id: number, fn: () => Promise<unknown>, message?: string) => {
    setBusyId(id);
    setError('');
    setNotice('');
    try {
      await fn();
      load();
      if (message) setNotice(message);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'That action could not be completed');
    } finally {
      setBusyId(null);
    }
  };

  const toggleActive = async (u: AdminUser) => {
    setBusyId(u.id);
    setError('');
    setNotice('');
    try {
      const r = await api.adminSetUserActive(u.id, !u.is_active);
      load();
      setNotice(
        !u.is_active
          ? `${u.name} is active again. ${r.listings_affected} listing${r.listings_affected === 1 ? '' : 's'} restored.`
          : `${u.name} is deactivated. ${r.listings_affected} listing${r.listings_affected === 1 ? '' : 's'} suspended.`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : 'That action could not be completed');
    } finally {
      setBusyId(null);
    }
  };

  const toggleVerified = async (u: AdminUser) => {
    const next = u.verification_status === 'verified' ? 'unverified' : 'verified';
    await run(
      u.id,
      () => api.adminSetUserVerification(u.id, next),
      next === 'verified'
        ? `${u.name} is now a verified farmer. Their listings show the badge.`
        : `${u.name} is no longer verified. The badge is gone from their listings.`,
    );
  };

  const setListingStatus = (l: AdminListing, status: ListingModerationStatus, note?: string, cancel?: boolean) =>
    run(l.id, () => api.adminSetListingStatus(l.id, status, note, cancel), `${l.title} is now ${STATUS_LABEL[status].toLowerCase()}.`);

  const attemptRemove = async (l: AdminListing) => {
    setError('');
    setNotice('');
    if (l.open_orders === 0) {
      await setListingStatus(l, 'removed');
      return;
    }
    setConfirmRemove({ listing: l, reason: '' });
  };

  const confirmRemoval = async () => {
    if (!confirmRemove) return;
    const { listing, reason } = confirmRemove;
    setConfirmRemove(null);
    await setListingStatus(listing, 'removed', reason || undefined, true);
  };

  const addCategory = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const d = new FormData(form);
    setError('');
    try {
      await api.adminCreateCategory(String(d.get('name')), Number(d.get('lifespan')));
      form.reset();
      load();
      setNotice('Category added.');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to add that category');
    }
  };

  const renameCategory = async (c: Category) => {
    const next = window.prompt(`Rename "${c.name}" to:`, c.name);
    if (next === null || next.trim() === '' || next === c.name) return;
    await run(c.id, () => api.adminUpdateCategory(c.id, next.trim()), 'Category renamed.');
  };

  const deleteCategory = async (c: Category) => {
    await run(c.id, () => api.adminDeleteCategory(c.id), 'Category deleted.');
  };

  const cancelSubscription = async (s: Subscription) => {
    await run(
      s.id,
      () => api.adminCancelSubscription(s.id),
      `${s.buyer_name}'s ${s.category} subscription cancelled. Cycles already ordered are unaffected.`,
    );
  };

  const closeReport = async () => {
    if (!closingReport) return;
    const { report, note } = closingReport;
    setClosingReport(null);
    await run(
      report.id,
      () => api.resolveReport(report.id, 'resolved', note || undefined),
      'Report closed.',
    );
  };

  const dismissReport = async (r: Report) => {
    await run(r.id, () => api.resolveReport(r.id, 'dismissed'), 'Report dismissed.');
  };

  const transitionOrder = (o: Order, next: string) =>
    run(o.id, () => api.updateOrderStatus(o.id, next as Order['status']), `Order #${o.id} marked ${next}.`);

  return (
    <main className="page">
      <div className="page-intro">
        <span className="eyebrow">Admin</span>
        <h1>Moderation</h1>
        <p>Signed in as {user.name}.</p>
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

      {tab === 'metrics' && metrics && (
        <div className="metrics">
          <div>
            <span>Users</span>
            <strong>{metrics.users}</strong>
            <small>All accounts</small>
          </div>
          <div>
            <span>Listings</span>
            <strong>{metrics.listings}</strong>
            <small>Including suspended</small>
          </div>
          <div>
            <span>Orders</span>
            <strong>{metrics.orders}</strong>
            <small>All time</small>
          </div>
          <div>
            <span>Open reports</span>
            <strong>{metrics.reports_open}</strong>
            <small>Awaiting review</small>
          </div>
          <div>
            <span>Categories</span>
            <strong>{metrics.categories}</strong>
            <small>Produce types</small>
          </div>
          <div>
            <span>Active subscriptions</span>
            <strong>{metrics.subscriptions}</strong>
            <small>Recurring boxes</small>
          </div>
          <div>
            <span>Open deliveries</span>
            <strong>{metrics.deliveries_open}</strong>
            <small>Not yet delivered</small>
          </div>
        </div>
      )}

      {tab === 'users' && (
        <div style={{ display: 'grid', gap: 12 }}>
          {users.map((u) => {
            const isSelf = u.id === user.id;
            const isAdmin = u.role === 'admin';
            const blocked = isSelf || isAdmin;
            const isFarmer = u.role === 'farmer';
            const isVerified = u.verification_status === 'verified';
            return (
              <article className="order-card" key={u.id}>
                <div className="order-head">
                  <strong>
                    {u.name}
                    {!u.is_active && <span className="badge expired" style={{ marginLeft: 8 }}>Deactivated</span>}
                    {isFarmer && isVerified && (
                      <span className="order-status accepted" style={{ marginLeft: 8 }}>Verified</span>
                    )}
                  </strong>
                  <span className={`order-status ${u.role === 'admin' ? 'accepted' : ''}`}>{u.role}</span>
                </div>
                <p className="muted">
                  {u.email} · {u.listing_count} listings · {u.report_count} reports
                </p>
                <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                  <button
                    className={u.is_active ? 'text-button' : 'button small'}
                    onClick={() => toggleActive(u)}
                    disabled={blocked || busyId === u.id}
                    title={isSelf ? 'You cannot deactivate yourself' : isAdmin ? 'Admin accounts cannot be deactivated' : undefined}
                  >
                    {busyId === u.id ? 'Working…' : u.is_active ? 'Deactivate' : 'Reactivate'}
                  </button>

                  {isFarmer && (
                    <button
                      className={isVerified ? 'text-button' : 'button small'}
                      onClick={() => toggleVerified(u)}
                      disabled={busyId === u.id}
                      title={isVerified ? 'Remove the verified badge from this farmer' : 'Grant the verified badge to this farmer'}
                    >
                      {busyId === u.id ? 'Working…' : isVerified ? 'Remove verification' : 'Verify farmer'}
                    </button>
                  )}
                  {blocked && (
                    <span className="muted">
                      {isSelf ? 'That is your own account.' : 'Admin accounts are protected.'}
                    </span>
                  )}
                  {!isSelf && u.role === 'farmer' && u.is_active && u.listing_count > 0 && (
                    <span className="muted">
                      Deactivating will suspend their {u.listing_count} listing
                      {u.listing_count === 1 ? '' : 's'}.
                    </span>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}

      {tab === 'listings' && confirmRemove && (
        <div className="result-banner has-failures" style={{ marginBottom: 20 }}>
          <p>
            <b>{confirmRemove.listing.title}</b> has {confirmRemove.listing.open_orders} open{' '}
            {confirmRemove.listing.open_orders === 1 ? 'order' : 'orders'}. Removing it will cancel{' '}
            {confirmRemove.listing.open_orders === 1 ? 'that order' : 'those orders'} and restore their reserved
            stock.
          </p>
          <label style={{ display: 'grid', gap: 6, marginTop: 10, fontWeight: 600 }}>
            Reason (optional)
            <input
              value={confirmRemove.reason}
              onChange={(e) => setConfirmRemove({ ...confirmRemove, reason: e.target.value })}
              placeholder="Why is this being removed?"
              style={{ padding: 10, border: '1px solid #cfdccb', borderRadius: 5, background: '#fff', font: 'inherit' }}
            />
          </label>
          <div style={{ display: 'flex', gap: 12, marginTop: 12 }}>
            <button className="button" onClick={confirmRemoval}>
              Remove and cancel orders
            </button>
            <button className="text-button" onClick={() => setConfirmRemove(null)}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {tab === 'listings' && (
        <div style={{ display: 'grid', gap: 12 }}>
          {listings.map((l) => (
            <article className="order-card" key={l.id}>
              <div className="order-head">
                <strong>{l.title}</strong>
                <span className={`order-status ${l.status === 'active' ? 'accepted' : l.status === 'removed' ? 'rejected' : 'requested'}`}>
                  {STATUS_LABEL[l.status]}
                </span>
              </div>
              <p className="muted">
                {l.farmer_name} · {l.category} · Rs {l.price_per_unit}/{l.unit} · {l.location}
              </p>
              <p style={{ margin: 0 }}>
                {l.available_quantity} {l.unit} ready
                {l.open_orders > 0 && <span className="muted"> · {l.open_orders} open orders</span>}
              </p>
              {l.moderation_note && <p className="muted">Note: {l.moderation_note}</p>}
              <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                <Link className="inline-link" to={`/listings/${l.id}`}>
                  View
                </Link>
                {l.status !== 'active' && (
                  <button className="button small" onClick={() => setListingStatus(l, 'active')} disabled={busyId === l.id}>
                    {busyId === l.id ? 'Working…' : 'Restore'}
                  </button>
                )}
                {l.status === 'active' && (
                  <button className="text-button" onClick={() => setListingStatus(l, 'suspended')} disabled={busyId === l.id}>
                    {busyId === l.id ? 'Working…' : 'Suspend'}
                  </button>
                )}
                {l.status !== 'removed' && (
                  <button className="text-button" onClick={() => attemptRemove(l)} disabled={busyId === l.id}>
                    {busyId === l.id ? 'Working…' : 'Remove'}
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
      )}

      {tab === 'orders' && (
        <>
          {!orders.length && <div className="empty">No orders exist yet.</div>}
          <div style={{ display: 'grid', gap: 12 }}>
            {orders.map((o) => (
              <article className="order-card" key={o.id}>
                <div className="order-head">
                  <strong>{o.listing_title}</strong>
                  <span className={`order-status ${o.status}`}>{o.status}</span>
                </div>
                <p className="muted">
                  {o.counterparty} → {o.farmer_name} · #{o.id} · {shortDate(o.created_at)}
                </p>
                <p style={{ margin: 0 }}>
                  {o.quantity} · <strong>Rs {o.total_amount.toFixed(2)}</strong>
                </p>
                <p className="muted" style={{ margin: 0 }}>
                  {o.delivery_method === 'pickup'
                    ? 'Pickup'
                    : `Delivery${o.delivery_status ? ` · ${o.delivery_status}` : ''}`}
                </p>
                <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                  <Link className="inline-link" to={`/listings/${o.listing_id}`}>
                    View listing
                  </Link>
                  {o.status === 'requested' && (
                    <>
                      <button className="button small" onClick={() => transitionOrder(o, 'accepted')} disabled={busyId === o.id}>
                        Accept
                      </button>
                      <button className="text-button" onClick={() => transitionOrder(o, 'rejected')} disabled={busyId === o.id}>
                        Reject
                      </button>
                    </>
                  )}
                  {o.status === 'accepted' && (
                    <button className="button small" onClick={() => transitionOrder(o, 'completed')} disabled={busyId === o.id}>
                      Mark completed
                    </button>
                  )}
                  {(o.status === 'requested' || o.status === 'accepted') && (
                    <button className="text-button" onClick={() => transitionOrder(o, 'cancelled')} disabled={busyId === o.id}>
                      Cancel
                    </button>
                  )}
                </div>
              </article>
            ))}
          </div>
        </>
      )}

      {tab === 'categories' && (
        <>
          <form className="auth" style={{ margin: '0 0 24px', padding: 0, maxWidth: 520 }} onSubmit={addCategory}>
            <h2 style={{ fontSize: '1rem', margin: 0 }}>Add a category</h2>
            <label>
              Name
              <input name="name" required placeholder="Bitter Gourd" />
            </label>
            <label>
              Default useful life (hours)
              <input name="lifespan" type="number" min="1" max="720" required defaultValue={48} />
            </label>
            <button className="button" type="submit">
              Add category
            </button>
          </form>

          <div style={{ display: 'grid', gap: 12 }}>
            {categories.map((c) => (
              <div className="order-card" key={c.id}>
                <div className="order-head">
                  <strong>{c.name}</strong>
                  <span className="muted">{c.default_lifespan_hours}h default</span>
                </div>
                <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                  <button className="text-button" onClick={() => renameCategory(c)} disabled={busyId === c.id}>
                    Rename
                  </button>
                  <button className="text-button" onClick={() => deleteCategory(c)} disabled={busyId === c.id}>
                    {busyId === c.id ? 'Working…' : 'Delete'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {tab === 'reports' && closingReport && (
        <div className="result-banner" style={{ marginBottom: 20 }}>
          <p style={{ margin: 0 }}>
            Closing the report on <b>{closingReport.report.listing_title}</b>. This records that you looked at it.
            It does not change the listing or the farmer.
          </p>
          <label style={{ display: 'grid', gap: 6, marginTop: 10, fontWeight: 600 }}>
            Note (optional)
            <input
              value={closingReport.note}
              onChange={(e) => setClosingReport({ ...closingReport, note: e.target.value })}
              placeholder="What did you find?"
              style={{ padding: 10, border: '1px solid #cfdccb', borderRadius: 5, background: '#fff', font: 'inherit' }}
            />
          </label>
          <div style={{ display: 'flex', gap: 12, marginTop: 12 }}>
            <button className="button" onClick={closeReport}>
              Close report
            </button>
            <button className="text-button" onClick={() => setClosingReport(null)}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {tab === 'reports' && (
        <>
          {!reports.length && <div className="empty">No reports have been filed.</div>}
          <div style={{ display: 'grid', gap: 12 }}>
            {reports.map((r) => (
              <article className="order-card" key={r.id}>
                <div className="order-head">
                  <strong>{r.listing_title}</strong>
                  <span className={`order-status ${r.status === 'open' ? 'requested' : 'completed'}`}>{r.status}</span>
                </div>
                <p className="muted">
                  {r.reporter} reported {r.reported_user} · {r.reason.replace(/_/g, ' ')}
                </p>
                {r.details && <p style={{ margin: 0 }}>{r.details}</p>}
                {r.resolution_note && <p className="muted">Note: {r.resolution_note}</p>}
                <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                  <Link className="inline-link" to={`/listings/${r.listing_id}`}>
                    Open the listing
                  </Link>
                  {r.status === 'open' && (
                    <>
                      <button className="button small" onClick={() => setClosingReport({ report: r, note: '' })} disabled={busyId === r.id}>
                        Resolve
                      </button>
                      <button className="text-button" onClick={() => dismissReport(r)} disabled={busyId === r.id}>
                        {busyId === r.id ? 'Working…' : 'Dismiss'}
                      </button>
                    </>
                  )}
                </div>
              </article>
            ))}
          </div>
        </>
      )}

      {tab === 'subscriptions' && (
        <>
          {!subscriptions.length && <div className="empty">No subscriptions exist yet.</div>}
          <div style={{ display: 'grid', gap: 12 }}>
            {subscriptions.map((s) => (
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
                  {s.buyer_name} &rarr; {s.farmer_name} · every {s.frequency_days} days
                </p>
                <p className="muted" style={{ margin: 0 }}>
                  {s.status === 'active'
                    ? `Next cycle ${shortDate(s.next_cycle_at)}`
                    : `Cancelled ${s.cancelled_at ? shortDate(s.cancelled_at) : ''}`}
                </p>
                {s.status === 'active' && (
                  <button className="text-button" onClick={() => cancelSubscription(s)} disabled={busyId === s.id}>
                    {busyId === s.id ? 'Working…' : 'Cancel subscription'}
                  </button>
                )}
              </article>
            ))}
          </div>
        </>
      )}
    </main>
  );
}
