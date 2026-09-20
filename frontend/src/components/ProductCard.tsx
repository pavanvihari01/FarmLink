import { Link } from 'react-router-dom';
import { ArrowRight, BadgeCheck, MapPin } from 'lucide-react';
import type { Listing } from '../types';

function freshnessClass(s: string) {
  return `badge ${s.toLowerCase().replace(' ', '-')}`;
}

export default function ProductCard({
  item,
  onAddToCart,
  onReport,
}: {
  item: Listing;
  onAddToCart?: (item: Listing) => void;
  onReport?: (item: Listing) => void;
}) {
  const href = `/listings/${item.id}`;

  return (
    <article className="product-card">
      <Link to={href}>
        <img src={item.image_url} alt={item.title} />
      </Link>
      <div className="product-body">
        <div className="card-top">
          <span className={freshnessClass(item.freshness_status)}>{item.freshness_status}</span>
          {item.verified && <BadgeCheck size={18} className="verified" aria-label="Verified farmer" />}
        </div>
        <h3>
          <Link to={href}>{item.title}</Link>
        </h3>
        <p className="muted">{item.farmer_name}</p>
        <p className="location">
          <MapPin size={15} />
          {item.location}
        </p>
        {typeof item.distance_km === 'number' && (
          <p className="muted">{item.distance_km} km from you</p>
        )}
        <div className="product-meta">
          <strong>
            Rs {item.price_per_unit}
            <small>/{item.unit}</small>
          </strong>
          <span>
            {item.available_quantity} {item.unit} ready
          </span>
        </div>
        <p className="life">{item.remaining_hours}h useful life remaining</p>
        {/* Only the recommendations endpoint sets a reason, so this stays out
            of the way everywhere else rather than repeating a stock line. */}
        {item.reason && (
          <p className="muted" style={{ margin: 0, fontSize: '.76rem' }}>{item.reason}</p>
        )}
        {onAddToCart ? (
          <button className="button small" onClick={() => onAddToCart(item)}>
            Add to cart <ArrowRight size={16} />
          </button>
        ) : (
          <Link className="button small" to={href}>
            View produce <ArrowRight size={16} />
          </Link>
        )}
        {onReport && (
          <button
            className="text-button"
            style={{ fontSize: '.72rem', marginTop: 8, color: '#8a9490' }}
            onClick={() => onReport(item)}
          >
            Report this listing
          </button>
        )}
      </div>
    </article>
  );
}
