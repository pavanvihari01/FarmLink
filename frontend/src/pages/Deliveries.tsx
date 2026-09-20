import { useEffect, useState } from 'react';
import { CircleMarker, MapContainer, Polyline, TileLayer } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { api } from '../lib/api';
import type { DeliveryRoute, DeliveryStatus, DeliveryStop, User } from '../types';

const DEFAULT_CENTER: [number, number] = [19.9975, 73.7898];

const STATUS_LABEL: Record<DeliveryStatus, string> = {
  pending: 'Pending',
  out_for_delivery: 'Out for delivery',
  delivered: 'Delivered',
  failed: 'Failed',
};

function statusClass(s: DeliveryStatus | null) {
  if (s === 'delivered') return 'order-status completed';
  if (s === 'failed') return 'order-status rejected';
  if (s === 'out_for_delivery') return 'order-status accepted';
  return 'order-status requested';
}

export default function Deliveries({ user }: { user: User }) {
  const [route, setRoute] = useState<DeliveryRoute | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busyId, setBusyId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setError('');
    api
      .deliveryRoute()
      .then(setRoute)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Unable to load deliveries'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const advance = async (stop: DeliveryStop, status: DeliveryStatus, note?: string) => {
    setBusyId(stop.order_id);
    setError('');
    setNotice('');
    try {
      await api.updateDeliveryStatus(stop.order_id, status, note);
      load();
      setNotice(`Order #${stop.order_id} marked ${STATUS_LABEL[status].toLowerCase()}.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'That delivery could not be updated');
    } finally {
      setBusyId(null);
    }
  };

  const fail = (stop: DeliveryStop) => {
    const note = window.prompt('Why did the delivery fail?', '');
    if (note === null) return;
    advance(stop, 'failed', note || undefined);
  };

  const stops = route?.stops ?? [];
  const origin = route?.origin ?? null;

  // The map centre: the origin when there is one, otherwise the first stop,
  // otherwise the demo centre.
  const center: [number, number] = origin
    ? [origin.latitude, origin.longitude]
    : stops.length
      ? [stops[0].latitude as number, stops[0].longitude as number]
      : DEFAULT_CENTER;

  const line: [number, number][] = origin
    ? [[origin.latitude, origin.longitude], ...stops.map((s) => [s.latitude as number, s.longitude as number] as [number, number])]
    : [];

  return (
    <main className="page">
      <div className="page-intro">
        <span className="eyebrow">Deliveries</span>
        <h1>Today&rsquo;s run</h1>
        <p>
          Accepted orders you are delivering. The suggested order is nearest-first from your most recently
          pinned listing — ignore it if you know a better way.
        </p>
      </div>

      {error && <p className="error">{error}</p>}
      {notice && <p className="result-banner">{notice}</p>}

      {loading && <div className="empty">Loading…</div>}

      {!loading && route && (
        <>
          {route.note && <div className="result-banner">{route.note}</div>}

          {route.total_distance_km !== null && stops.length > 0 && (
            <p className="result-count">
              {stops.length} {stops.length === 1 ? 'stop' : 'stops'} · about {route.total_distance_km} km total
              (straight-line, not road distance)
            </p>
          )}

          {stops.length > 0 && (
            <div style={{ borderRadius: 7, overflow: 'hidden', border: '1px solid #d9e5d5', marginBottom: 24 }}>
              <MapContainer center={center} zoom={9} scrollWheelZoom={false} style={{ height: 380, width: '100%' }}>
                <TileLayer
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />
                {/* The route line, origin first. CircleMarker and Polyline are
                    both pure SVG — no icon assets to go missing under Vite. */}
                {line.length > 1 && <Polyline positions={line} pathOptions={{ color: '#23643e', weight: 3 }} />}
                {origin && (
                  <CircleMarker
                    center={[origin.latitude, origin.longitude]}
                    radius={9}
                    pathOptions={{ color: '#1b5235', weight: 3, fillColor: '#1b5235', fillOpacity: 0.85 }}
                  />
                )}
                {stops.map((s) => (
                  <CircleMarker
                    key={s.order_id}
                    center={[s.latitude as number, s.longitude as number]}
                    radius={8}
                    pathOptions={{ color: '#23643e', weight: 2, fillColor: '#d6eb5f', fillOpacity: 0.9 }}
                  />
                ))}
              </MapContainer>
            </div>
          )}

          {stops.length === 0 && !route.note && (
            <div className="empty">No deliveries in progress.</div>
          )}

          <div style={{ display: 'grid', gap: 14 }}>
            {stops.map((s, i) => (
              <article className="order-card" key={s.order_id}>
                <div className="order-head">
                  <strong>
                    {i + 1}. {s.listing_title}
                  </strong>
                  <span className={statusClass(s.delivery_status)}>
                    {s.delivery_status ? STATUS_LABEL[s.delivery_status] : 'Pending'}
                  </span>
                </div>
                <p className="muted">
                  {s.buyer_name} · Order #{s.order_id} · {s.quantity} to deliver
                </p>
                <p style={{ margin: 0 }}>{s.address}</p>
                <p className="muted" style={{ margin: 0 }}>
                  {typeof s.leg_distance_km === 'number'
                    ? `${s.leg_distance_km} km from the previous stop`
                    : 'Distance from the previous stop unavailable'}
                  {typeof s.distance_from_origin_km === 'number' &&
                    ` · ${s.distance_from_origin_km} km from your start`}
                </p>
                {s.delivery_note && <p className="muted" style={{ margin: 0 }}>{s.delivery_note}</p>}

                <div style={{ display: 'flex', gap: 10, marginTop: 12, flexWrap: 'wrap' }}>
                  {s.delivery_status === 'pending' && (
                    <button
                      className="button"
                      onClick={() => advance(s, 'out_for_delivery')}
                      disabled={busyId === s.order_id}
                    >
                      Start delivery
                    </button>
                  )}
                  {s.delivery_status === 'out_for_delivery' && (
                    <button
                      className="button"
                      onClick={() => advance(s, 'delivered')}
                      disabled={busyId === s.order_id}
                    >
                      Mark delivered
                    </button>
                  )}
                  {s.delivery_status !== 'delivered' && s.delivery_status !== 'failed' && (
                    <button
                      className="text-button"
                      onClick={() => fail(s)}
                      disabled={busyId === s.order_id}
                    >
                      Mark failed
                    </button>
                  )}
                </div>
              </article>
            ))}
          </div>

          {route.unroutable.length > 0 && (
            <>
              <h2 style={{ marginTop: 28 }}>Not on the map</h2>
              <p className="muted">
                These orders have no delivery pin, so they cannot be placed on the route. Their address is
                shown so you can still reach them.
              </p>
              <div style={{ display: 'grid', gap: 14 }}>
                {route.unroutable.map((s) => (
                  <article className="order-card" key={s.order_id}>
                    <div className="order-head">
                      <strong>{s.listing_title}</strong>
                      <span className={statusClass(s.delivery_status)}>
                        {s.delivery_status ? STATUS_LABEL[s.delivery_status] : 'Pending'}
                      </span>
                    </div>
                    <p className="muted" style={{ margin: 0 }}>
                      {s.buyer_name} · Order #{s.order_id} · {s.quantity} to deliver
                    </p>
                    <p style={{ margin: 0 }}>{s.address}</p>
                  </article>
                ))}
              </div>
            </>
          )}
        </>
      )}
    </main>
  );
}
