import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Pencil, TrendingDown, TrendingUp, Minus } from 'lucide-react';
import ProductCard from '../components/ProductCard';
import { api } from '../lib/api';
import type { DashboardSummary, Forecast as ForecastData, ForecastTrend, Listing, User } from '../types';

type Card = { label: string; value: number | undefined; hint: string };

function TrendIcon({ trend }: { trend: ForecastTrend }) {
  if (trend === 'rising') return <TrendingUp size={14} />;
  if (trend === 'falling') return <TrendingDown size={14} />;
  return <Minus size={14} />;
}

export default function Dashboard({ user, items }: { user: User; items: Listing[] }) {
  const isFarmer = user.role === 'farmer';

  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [forecast, setForecast] = useState<ForecastData | null>(null);
  const [own, setOwn] = useState<Listing[]>([]);
  const [recommended, setRecommended] = useState<Listing[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    setError('');
    api
      .summary()
      .then(setSummary)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Unable to load your metrics'));
    // Ranked on this buyer's own order history. Falls back to the featured
    // listings below until it arrives, so the section never flashes empty.
    api.recommendations().then(setRecommended).catch(() => undefined);
    if (isFarmer) {
      api.forecast().then(setForecast).catch(() => undefined);
      // The public /listings endpoint only returns active, non-expired rows,
      // so a farmer cannot see their own suspended or expired stock through it.
      api.farmerListings().then(setOwn).catch(() => undefined);
    }
  }, [isFarmer]);

  const cards: Card[] = isFarmer
    ? [
        { label: 'Active listings', value: summary?.active_listings, hint: 'Live and not expired' },
        { label: 'Open orders', value: summary?.open_orders, hint: 'Awaiting your response' },
        { label: 'Expired listings', value: summary?.expired_listings, hint: 'Past their freshness window' },
      ]
    : [
        { label: 'Available now', value: summary?.available_now, hint: 'Fresh listings today' },
        { label: 'Open orders', value: summary?.open_orders, hint: 'Requests in progress' },
        { label: 'Categories', value: summary?.categories, hint: 'Produce in season' },
      ];

  const topForecast = forecast?.items.slice(0, 3) ?? [];
  const rec = recommended.length ? recommended : items.slice(0, 3);

  return (
    <main className="page">
      <div className="dashboard-head">
        <div>
          <span className="eyebrow">{user.role} workspace</span>
          <h1>Hello, {user.name.split(' ')[0]}.</h1>
          <p>{isFarmer ? 'Your harvest has real demand today.' : 'Here is what is freshest near you.'}</p>
        </div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {isFarmer && (
            <Link to="/listings/new" className="button small">
              Create listing
            </Link>
          )}
          <Link to="/marketplace" className="button small">
            Go to marketplace
          </Link>
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      <div className="metrics">
        {cards.map((c) => (
          <div key={c.label}>
            <span>{c.label}</span>
            <strong>{c.value === undefined ? '\u2014' : c.value}</strong>
            <small>{c.hint}</small>
          </div>
        ))}
      </div>

      {isFarmer && own.length > 0 && (
        <section className="dashboard-section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">Your listings</span>
              <h2>{own.length} in total</h2>
            </div>
          </div>
          <div style={{ display: 'grid', gap: 10 }}>
            {own.map((l) => (
              <div
                key={l.id}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: 12,
                  flexWrap: 'wrap',
                  background: '#fff',
                  border: '1px solid #e1e9de',
                  borderRadius: 7,
                  padding: '12px 16px',
                }}
              >
                <span>
                  <b>{l.title}</b>
                  <span className="muted"> · {l.available_quantity} {l.unit} · Rs {l.price_per_unit}/{l.unit}</span>
                </span>
                <span style={{ display: 'inline-flex', gap: 10, alignItems: 'center' }}>
                  {l.status && l.status !== 'active' && <span className="badge expired">{l.status}</span>}
                  {l.status !== 'removed' && (
                    <Link className="inline-link" to={`/listings/${l.id}/edit`}>
                      <Pencil size={15} /> Edit
                    </Link>
                  )}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {isFarmer && forecast && topForecast.length > 0 && (
        <section className="dashboard-section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">Demand forecast</span>
              <h2>What buyers are likely to want</h2>
            </div>
            <Link to="/forecast" className="inline-link">
              Full forecast
            </Link>
          </div>

          {forecast.note && <p className="muted">{forecast.note}</p>}

          <div style={{ display: 'grid', gap: 10 }}>
            {topForecast.map((item) => (
              <div
                key={`${item.category_id}-${item.location}-${item.unit}`}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: 12,
                  background: '#fff',
                  border: '1px solid #e1e9de',
                  borderRadius: 7,
                  padding: '12px 16px',
                }}
              >
                <span>
                  <b>{item.category}</b>
                  <span className="muted"> — {item.location}</span>
                </span>
                <span style={{ display: 'inline-flex', gap: 8, alignItems: 'center' }}>
                  <span className="muted" style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
                    <TrendIcon trend={item.trend} />
                  </span>
                  <strong>
                    ~{item.weekly_rate} {item.unit}
                  </strong>
                  <span className="muted">/week</span>
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {isFarmer && forecast && topForecast.length === 0 && (
        <section className="dashboard-section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">Demand forecast</span>
              <h2>What buyers are likely to want</h2>
            </div>
          </div>
          <div className="empty">{forecast.note ?? 'Not enough order history yet to forecast anything.'}</div>
        </section>
      )}

      <section className="dashboard-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Recommended for you</span>
            <h2>Worth a closer look</h2>
          </div>
        </div>
        <div className="product-grid">
          {rec.map((x) => (
            <ProductCard item={x} key={x.id} />
          ))}
        </div>
      </section>
    </main>
  );
}
