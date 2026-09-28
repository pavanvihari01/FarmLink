import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowRight, BadgeCheck, Leaf, MapPin, Package, Pencil } from 'lucide-react';
import { api } from '../lib/api';
import { useCart } from '../context/CartContext';
import type { Listing, User } from '../types';

function freshnessClass(s: string) {
  return `badge ${s.toLowerCase().replace(' ', '-')}`;
}

export default function ListingDetail({ user }: { user: User | null }) {
  const { listingId } = useParams();
  const nav = useNavigate();
  const { add } = useCart();

  const [listing, setListing] = useState<Listing | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [error, setError] = useState('');
  const [added, setAdded] = useState(false);

  useEffect(() => {
    const id = Number(listingId);
    if (!id) {
      setError('That listing link is not valid.');
      return;
    }
    setError('');
    setListing(null);
    api
      .listing(id)
      .then((x) => {
        setListing(x);
        setQuantity(1);
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'That listing could not be found.'));
  }, [listingId]);

  if (error) {
    return (
      <main className="page">
        <div className="page-intro">
          <span className="eyebrow">Listing</span>
          <h1>Not available</h1>
          <p>{error}</p>
        </div>
        <Link className="button" to="/marketplace">
          Back to marketplace
        </Link>
      </main>
    );
  }

  if (!listing) {
    return (
      <main className="page">
        <div className="empty">Loading…</div>
      </main>
    );
  }

  const isOwner = user !== null && user.id === listing.farmer_id;

  const max = Math.max(1, Math.floor(listing.available_quantity));
  const clamped = Math.min(Math.max(1, quantity), max);

  const addToCart = () => {
    add(
      {
        listing_id: listing.id,
        title: listing.title,
        price_per_unit: listing.price_per_unit,
        unit: listing.unit,
        image_url: listing.image_url,
        farmer_name: listing.farmer_name,
        available_quantity: listing.available_quantity,
      },
      clamped,
    );
    setAdded(true);
    setTimeout(() => setAdded(false), 2500);
  };

  return (
    <main className="page">
      <p className="muted" style={{ marginBottom: 12 }}>
        <Link to="/marketplace">Marketplace</Link> · {listing.category}
      </p>

      <div className="listing-layout">
        <div>
          <img
            src={listing.image_url}
            alt={listing.title}
            style={{ width: '100%', borderRadius: 8, border: '1px solid #e1e9de', display: 'block' }}
          />
        </div>

        <div style={{ display: 'grid', gap: 14 }}>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
            <span className={freshnessClass(listing.freshness_status)}>{listing.freshness_status}</span>
            {listing.status && listing.status !== 'active' && (
              <span className="badge expired">{listing.status}</span>
            )}
            {listing.verified && (
              <span className="muted" style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
                <BadgeCheck size={16} className="verified" /> Verified farmer
              </span>
            )}
          </div>

          <h1 style={{ margin: 0 }}>{listing.title}</h1>

          <p className="muted" style={{ margin: 0 }}>
            Sold by <b>{listing.farmer_name}</b>
          </p>

          <p className="location" style={{ margin: 0 }}>
            <MapPin size={15} /> {listing.location}
          </p>

          {listing.description && <p style={{ margin: 0 }}>{listing.description}</p>}

          <div className="cart-summary">
            <div className="row">
              <span>Price</span>
              <span>
                <strong>
                  Rs {listing.price_per_unit}
                  <small>/{listing.unit}</small>
                </strong>
              </span>
            </div>
            <div className="row">
              <span>Available</span>
              <span>
                {listing.available_quantity} {listing.unit}
              </span>
            </div>
            <div className="row">
              <span>Useful life left</span>
              <span>{listing.remaining_hours} hours</span>
            </div>
            {typeof listing.distance_km === 'number' && (
              <div className="row">
                <span>Distance</span>
                <span>{listing.distance_km} km</span>
              </div>
            )}
            {(listing.organic || listing.bulk_available) && (
              <div className="row">
                <span>Good to know</span>
                <span style={{ display: 'flex', gap: 10 }}>
                  {listing.organic && (
                    <span className="muted" style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
                      <Leaf size={14} /> Organic
                    </span>
                  )}
                  {listing.bulk_available && (
                    <span className="muted" style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
                      <Package size={14} /> Bulk
                    </span>
                  )}
                </span>
              </div>
            )}

            {listing.moderation_note && <p className="muted" style={{ margin: 0 }}>{listing.moderation_note}</p>}

            {isOwner ? (
              <>
                <p className="muted" style={{ margin: 0 }}>
                  This is your listing.
                </p>
                <Link className="button" to={`/listings/${listing.id}/edit`}>
                  <Pencil size={16} /> Edit listing
                </Link>
              </>
            ) : (
              <>
                <label style={{ display: 'grid', gap: 6, fontWeight: 700, fontSize: '.86rem', color: '#385342' }}>
                  Quantity ({listing.unit})
                  <input
                    className="qty-input"
                    style={{ width: '100%' }}
                    type="number"
                    min={1}
                    max={max}
                    step={listing.unit === 'kg' ? 0.5 : 1}
                    value={clamped}
                    onChange={(e) => setQuantity(Number(e.target.value))}
                    aria-label={`Quantity in ${listing.unit}`}
                  />
                </label>

                <div className="row total">
                  <span>Subtotal</span>
                  <span>Rs {(clamped * listing.price_per_unit).toFixed(2)}</span>
                </div>

                <button className="button" onClick={addToCart}>
                  Add to cart <ArrowRight size={18} />
                </button>

                {added && (
                  <p className="muted" style={{ margin: 0 }}>
                    Added. <Link to="/cart">Go to cart</Link> to check out.
                  </p>
                )}

                <button className="text-button" onClick={() => nav(`/report/${listing.id}`)}>
                  Report this listing
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
