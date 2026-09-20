import { Link } from 'react-router-dom';
import { ArrowRight, Leaf, Sprout } from 'lucide-react';
import ProductCard from '../components/ProductCard';
import type { Listing } from '../types';

export default function Home({ items, liveCount }: { items: Listing[]; liveCount: number | null }) {
  return (
    <>
      <section className="hero">
        <div className="hero-copy">
          <span className="eyebrow">
            <Leaf size={16} /> Direct from the people who grow it
          </span>
          <h1>Fresh food. Fairer farms.</h1>
          <p>
            Buy vegetables directly from local farmers and FPOs. Better prices, clear freshness, and less waste
            along the way.
          </p>
          <div className="hero-actions">
            <Link className="button" to="/marketplace">
              Explore marketplace <ArrowRight size={18} />
            </Link>
            <Link className="link-button" to="/register">
              Join FarmLink
            </Link>
          </div>
          {/* One real figure rather than two invented ones. The count comes from
              the same listings response the featured cards do.
              "42 nearby farms" and "6h average harvest-to-order" were literal
              strings with nothing behind them — the first also claimed
              proximity the visitor's location was never used to establish. A
              second stat would need a join nothing computes, so there is one. */}
          {liveCount !== null && (
            <div className="hero-facts">
              <span>
                <strong>{liveCount}</strong> {liveCount === 1 ? 'listing' : 'listings'} ready now
              </span>
            </div>
          )}
        </div>
      </section>
      <section className="section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Harvested this week</span>
            <h2>Good food, close to home</h2>
          </div>
          <Link to="/marketplace" className="inline-link">
            Browse all <ArrowRight size={16} />
          </Link>
        </div>
        <div className="product-grid">
          {items.slice(0, 4).map((x) => (
            <ProductCard item={x} key={x.id} />
          ))}
        </div>
      </section>
      <section className="impact">
        <div>
          <Sprout size={30} />
          <h2>One marketplace. Better outcomes.</h2>
        </div>
        <p>
          FarmLink helps growers sell directly, helps buyers see where food comes from, and keeps delivery planning
          simple.
        </p>
        <div className="impact-items">
          <span>
            <b>Direct prices</b>No unnecessary middle layers
          </span>
          <span>
            <b>Freshness first</b>Clear shelf-life indicators
          </span>
          <span>
            <b>Smarter delivery</b>Practical route planning
          </span>
        </div>
      </section>
    </>
  );
}
