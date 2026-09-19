import { Link } from 'react-router-dom';
import ProductCard from '../components/ProductCard';
import type { Listing, User } from '../types';

export default function Dashboard({ user, items }: { user: User; items: Listing[] }) {
  const rec = items.slice(0, 3);

  return (
    <main className="page">
      <div className="dashboard-head">
        <div>
          <span className="eyebrow">{user.role} workspace</span>
          <h1>Hello, {user.name.split(' ')[0]}.</h1>
          <p>
            {user.role === 'farmer'
              ? 'Your harvest has real demand today.'
              : 'Here is what is freshest near you.'}
          </p>
        </div>
        <Link to="/marketplace" className="button small">
          Go to marketplace
        </Link>
      </div>
      <div className="metrics">
        <div>
          <span>Active listings</span>
          <strong>{user.role === 'farmer' ? '7' : '24'}</strong>
          <small>+2 this week</small>
        </div>
        <div>
          <span>Open orders</span>
          <strong>{user.role === 'farmer' ? '4' : '2'}</strong>
          <small>All on track</small>
        </div>
        <div>
          <span>{user.role === 'farmer' ? 'Expected demand' : 'Saved farms'}</span>
          <strong>{user.role === 'farmer' ? 'High' : '5'}</strong>
          <small>Tomato this week</small>
        </div>
      </div>
      <section className="dashboard-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Recommended for you</span>
            <h2>Worth a closer look</h2>
          </div>
        </div>
        <div className="product-grid">
          {rec.map((x) => (
            <ProductCard item={{ ...x, reason: 'Fresh today and close to you' }} key={x.id} />
          ))}
        </div>
      </section>
    </main>
  );
}
