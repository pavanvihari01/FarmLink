import { useEffect, useState } from 'react';
import { TrendingDown, TrendingUp, Minus } from 'lucide-react';
import { api } from '../lib/api';
import type { Forecast as ForecastData, ForecastItem, ForecastTrend, User } from '../types';

function TrendIcon({ trend }: { trend: ForecastTrend }) {
  if (trend === 'rising') return <TrendingUp size={16} />;
  if (trend === 'falling') return <TrendingDown size={16} />;
  return <Minus size={16} />;
}

function trendText(item: ForecastItem) {
  if (item.trend === 'steady') return 'Holding steady';
  if (item.trend_pct === null) return 'New demand — nothing to compare against';
  const sign = item.trend_pct > 0 ? '+' : '';
  return `${sign}${item.trend_pct}% versus the previous 4 weeks`;
}

function shortDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
}

export default function Forecast({ user }: { user: User }) {
  const [data, setData] = useState<ForecastData | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .forecast()
      .then(setData)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Unable to load your forecast'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="page">
      <div className="page-intro">
        <span className="eyebrow">Demand forecast</span>
        <h1>What buyers are likely to want</h1>
        <p>
          Built from orders placed with you over the last {data?.window_weeks ?? 8} weeks, projected{' '}
          {data?.forecast_weeks ?? 2} weeks forward. Every order counts, including ones you have not answered
          yet — only orders you rejected or that were cancelled are left out.
        </p>
      </div>

      {error && <p className="error">{error}</p>}

      {loading && <div className="empty">Loading…</div>}

      {data && (
        <>
          {data.note && <div className="result-banner">{data.note}</div>}

          {data.items.length === 0 && !data.note && (
            <div className="empty">No forecast to show.</div>
          )}

          {data.items.length > 0 && (
            <>
              <p className="result-count">
                {data.items.length} {data.items.length === 1 ? 'line' : 'lines'} ·{' '}
                {data.order_count} {data.order_count === 1 ? 'order' : 'orders'} in the window · generated{' '}
                {shortDate(data.generated_at)}
              </p>

              <div style={{ display: 'grid', gap: 14 }}>
                {data.items.map((item) => (
                  <article className="order-card" key={`${item.category_id}-${item.location}-${item.unit}`}>
                    <div className="order-head">
                      <strong>
                        {item.category} — {item.location}
                      </strong>
                      <span className="badge fresh">
                        ~{item.forecast_quantity} {item.unit}
                      </span>
                    </div>

                    <p style={{ margin: 0 }}>
                      About <strong>{item.weekly_rate} {item.unit}</strong> per week, over the next{' '}
                      {data.forecast_weeks} weeks.
                    </p>

                    <p className="muted" style={{ margin: 0 }}>
                      {item.order_count} {item.order_count === 1 ? 'order' : 'orders'} totalling{' '}
                      {item.past_quantity} {item.unit} in the last {data.window_weeks} weeks.
                    </p>

                    <p
                      className="muted"
                      style={{ margin: 0, display: 'inline-flex', gap: 6, alignItems: 'center' }}
                    >
                      <TrendIcon trend={item.trend} />
                      {trendText(item)}
                    </p>

                    <div className="row" style={{ display: 'flex', gap: 24, fontSize: '.86rem' }}>
                      <span>
                        Last 4 weeks: <strong>{item.recent_quantity} {item.unit}</strong>
                      </span>
                      <span>
                        The 4 before: <strong>{item.prior_quantity} {item.unit}</strong>
                      </span>
                    </div>

                    {!item.has_enough_data && (
                      <p className="muted" style={{ margin: 0 }}>
                        Only {item.order_count} {item.order_count === 1 ? 'order' : 'orders'} to go on. This is a
                        summary of what happened, not a prediction.
                      </p>
                    )}
                  </article>
                ))}
              </div>
            </>
          )}

          <section className="section" style={{ padding: 0, marginTop: 40 }}>
            <div className="section-heading">
              <div>
                <span className="eyebrow">How this works</span>
                <h2>What the number means</h2>
              </div>
            </div>
            <div className="cart-summary" style={{ maxWidth: 680 }}>
              <p style={{ margin: 0 }}>
                Orders from the last {data.window_weeks} weeks are grouped by category, location, and unit, then
                averaged into a weekly rate. That rate is multiplied by {data.forecast_weeks} to give the figure
                above.
              </p>
              <p className="muted" style={{ margin: 0 }}>
                Units are kept apart on purpose. 10 kg and 3 dozen are not 13 of anything, so they are never
                added together.
              </p>
              <p className="muted" style={{ margin: 0 }}>
                The trend compares the most recent 4 weeks against the 4 before it. A change under 15% is called
                steady, because a small wobble in a short window is noise rather than a direction.
              </p>
              <p className="muted" style={{ margin: 0 }}>
                With only a handful of orders, this is close to a restatement of the raw data. It gets more
                useful as order history grows.
              </p>
            </div>
          </section>
        </>
      )}
    </main>
  );
}
