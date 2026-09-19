import { ArrowRight, BadgeCheck, MapPin } from 'lucide-react';
import type { Listing } from '../types';

function freshnessClass(s: string) {
  return `badge ${s.toLowerCase().replace(' ', '-')}`;
}

export default function ProductCard({
  item,
  onOrder,
}: {
  item: Listing;
  onOrder?: (item: Listing) => void;
}) {
  return (
    <article className="product-card">
      <img src={item.image_url} alt={item.title} />
      <div className="product-body">
        <div className="card-top">
          <span className={freshnessClass(item.freshness_status)}>{item.freshness_status}</span>
          {item.verified && <BadgeCheck size={18} className="verified" aria-label="Verified farmer" />}
        </div>
        <h3>{item.title}</h3>
        <p className="muted">{item.farmer_name}</p>
        <p className="location">
          <MapPin size={15} />
          {item.location}
        </p>
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
        <button className="button small" onClick={() => onOrder?.(item)}>
          {onOrder ? 'Request order' : 'View produce'} <ArrowRight size={16} />
        </button>
      </div>
    </article>
  );
}
