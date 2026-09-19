import { useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import ProductCard from '../components/ProductCard';
import type { Listing } from '../types';

export default function Marketplace({ items, onOrder }: { items: Listing[]; onOrder: (i: Listing) => void }) {
  const [query, setQuery] = useState('');
  const [fresh, setFresh] = useState('');

  const filtered = useMemo(
    () =>
      items.filter(
        (x) =>
          (!query ||
            x.title.toLowerCase().includes(query.toLowerCase()) ||
            x.location.toLowerCase().includes(query.toLowerCase())) &&
          (!fresh || x.freshness_status === fresh)
      ),
    [items, query, fresh]
  );

  return (
    <main className="page">
      <div className="page-intro">
        <span className="eyebrow">Marketplace</span>
        <h1>Vegetables with a story</h1>
        <p>Meet the growers. Compare freshness. Order what you need.</p>
      </div>
      <div className="filters">
        <label>
          <Search size={18} />
          <input placeholder="Search produce or place" value={query} onChange={(e) => setQuery(e.target.value)} />
        </label>
        <select value={fresh} onChange={(e) => setFresh(e.target.value)}>
          <option value="">All freshness</option>
          <option>Fresh</option>
          <option>Use Soon</option>
          <option>Expiring</option>
        </select>
      </div>
      <p className="result-count">{filtered.length} listings available today</p>
      <div className="product-grid">
        {filtered.map((x) => (
          <ProductCard item={x} onOrder={onOrder} key={x.id} />
        ))}
      </div>
      {!filtered.length && <div className="empty">No produce matches those filters. Try a different search.</div>}
    </main>
  );
}
