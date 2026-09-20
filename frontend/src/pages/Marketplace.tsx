import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Search, SlidersHorizontal } from 'lucide-react';
import ProductCard from '../components/ProductCard';
import { useCart } from '../context/CartContext';
import { api } from '../lib/api';
import { useGeolocation } from '../lib/useGeolocation';
import type { Category, Listing, ListingSort, PaginatedListings } from '../types';

const PAGE_SIZE = 12;

const SORT_LABELS: { value: ListingSort; label: string }[] = [
  { value: 'freshness', label: 'Freshest first' },
  { value: 'price_asc', label: 'Price: low to high' },
  { value: 'price_desc', label: 'Price: high to low' },
  { value: 'newest', label: 'Newest listings' },
  { value: 'nearest', label: 'Nearest to me' },
];

type Filters = {
  categoryId: string;
  minPrice: string;
  maxPrice: string;
  organic: boolean;
  bulk: boolean;
  freshness: string;
  sort: ListingSort;
  page: number;
};

const INITIAL_FILTERS: Filters = {
  categoryId: '',
  minPrice: '',
  maxPrice: '',
  organic: false,
  bulk: false,
  freshness: '',
  sort: 'freshness',
  page: 1,
};

export default function Marketplace() {
  const nav = useNavigate();
  const { add } = useCart();
  const geo = useGeolocation();

  // Text inputs are held separately from the rest so the debounce below only
  // delays typing, not a sort or page change.
  const [text, setText] = useState({ q: '', location: '', farmer: '' });
  const [debouncedText, setDebouncedText] = useState(text);
  const [filters, setFilters] = useState<Filters>(INITIAL_FILTERS);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const [categories, setCategories] = useState<Category[]>([]);
  const [result, setResult] = useState<PaginatedListings | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedText(text), 350);
    return () => clearTimeout(timer);
  }, [text]);

  useEffect(() => {
    api.categories().then(setCategories).catch(() => undefined);
  }, []);

  // Any filter or sort change resets to page 1. Passing an explicit page is how
  // the pagination controls move without resetting.
  const update = (patch: Partial<Filters>) =>
    setFilters((prev) => ({ ...prev, ...patch, page: patch.page ?? 1 }));

  const useDistance = filters.sort === 'nearest';
  const origin = useDistance ? geo.point : null;

  const params = useMemo(
    () => ({
      q: debouncedText.q || undefined,
      location: debouncedText.location || undefined,
      farmer: debouncedText.farmer || undefined,
      category_id: filters.categoryId ? Number(filters.categoryId) : undefined,
      min_price: filters.minPrice ? Number(filters.minPrice) : undefined,
      max_price: filters.maxPrice ? Number(filters.maxPrice) : undefined,
      organic: filters.organic || undefined,
      bulk_available: filters.bulk || undefined,
      freshness_status: filters.freshness || undefined,
      sort: filters.sort,
      page: filters.page,
      page_size: PAGE_SIZE,
      lat: origin?.lat,
      lng: origin?.lng,
    }),
    [debouncedText, filters, origin],
  );

  useEffect(() => {
    // 'nearest' cannot be sent without a location, so wait rather than firing a
    // request the server will reject with 422.
    if (useDistance && !geo.point) return;

    let cancelled = false;
    setLoading(true);
    setError('');
    api
      .listings(params)
      .then((r) => {
        if (!cancelled) setResult(r);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Unable to load listings');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [params, useDistance, geo.point]);

  const addToCart = (item: Listing) =>
    add({
      listing_id: item.id,
      title: item.title,
      price_per_unit: item.price_per_unit,
      unit: item.unit,
      image_url: item.image_url,
      farmer_name: item.farmer_name,
      available_quantity: item.available_quantity,
    });

  const clearAll = () => {
    setText({ q: '', location: '', farmer: '' });
    setFilters(INITIAL_FILTERS);
  };

  const activeFilterCount =
    (filters.categoryId ? 1 : 0) +
    (filters.minPrice ? 1 : 0) +
    (filters.maxPrice ? 1 : 0) +
    (filters.organic ? 1 : 0) +
    (filters.bulk ? 1 : 0) +
    (filters.freshness ? 1 : 0) +
    (debouncedText.location ? 1 : 0) +
    (debouncedText.farmer ? 1 : 0);

  const items = result?.items ?? [];

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
          <input
            placeholder="Search produce or place"
            value={text.q}
            onChange={(e) => setText({ ...text, q: e.target.value })}
          />
        </label>
        <select value={filters.freshness} onChange={(e) => update({ freshness: e.target.value })}>
          <option value="">All freshness</option>
          <option>Fresh</option>
          <option>Use Soon</option>
          <option>Expiring</option>
        </select>
        <select value={filters.sort} onChange={(e) => update({ sort: e.target.value as ListingSort })}>
          {SORT_LABELS.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
        <button className="button small" type="button" onClick={() => setShowAdvanced((v) => !v)}>
          <SlidersHorizontal size={16} />
          {showAdvanced ? 'Hide filters' : 'More filters'}
          {activeFilterCount > 0 && <span className="badge fresh">{activeFilterCount}</span>}
        </button>
      </div>

      {showAdvanced && (
        <div className="filters" style={{ marginTop: 12, flexWrap: 'wrap' }}>
          <label>
            Category
            <select value={filters.categoryId} onChange={(e) => update({ categoryId: e.target.value })}>
              <option value="">All categories</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Min price
            <input
              type="number"
              min="0"
              value={filters.minPrice}
              onChange={(e) => update({ minPrice: e.target.value })}
              placeholder="0"
            />
          </label>
          <label>
            Max price
            <input
              type="number"
              min="0"
              value={filters.maxPrice}
              onChange={(e) => update({ maxPrice: e.target.value })}
              placeholder="Any"
            />
          </label>
          <label>
            Place
            <input
              value={text.location}
              onChange={(e) => setText({ ...text, location: e.target.value })}
              placeholder="Nashik"
            />
          </label>
          <label>
            Farmer
            <input
              value={text.farmer}
              onChange={(e) => setText({ ...text, farmer: e.target.value })}
              placeholder="Anita"
            />
          </label>
          <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontWeight: 400 }}>
            <input
              type="checkbox"
              checked={filters.organic}
              onChange={(e) => update({ organic: e.target.checked })}
            />
            Organic only
          </label>
          <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontWeight: 400 }}>
            <input
              type="checkbox"
              checked={filters.bulk}
              onChange={(e) => update({ bulk: e.target.checked })}
            />
            Bulk available
          </label>
          {activeFilterCount > 0 && (
            <button className="text-button" type="button" onClick={clearAll}>
              Clear all
            </button>
          )}
        </div>
      )}

      {useDistance && !geo.point && (
        <div className="result-banner" style={{ marginTop: 16 }}>
          {geo.status === 'denied' || geo.status === 'unsupported' ? (
            <>
              <p style={{ margin: 0 }}>{geo.error}</p>
              <button className="text-button" style={{ marginTop: 8 }} onClick={() => update({ sort: 'freshness' })}>
                Sort by freshness instead
              </button>
            </>
          ) : (
            <>
              <p style={{ margin: 0 }}>Share your location to sort by distance.</p>
              <button
                className="button small"
                style={{ marginTop: 8 }}
                onClick={geo.request}
                disabled={geo.status === 'asking'}
              >
                {geo.status === 'asking' ? 'Asking…' : 'Use my location'}
              </button>
            </>
          )}
        </div>
      )}

      {error && <p className="error">{error}</p>}

      {result && (
        <p className="result-count">
          {result.total} {result.total === 1 ? 'listing' : 'listings'} available today
          {result.pages > 1 && ` · page ${result.page} of ${result.pages}`}
        </p>
      )}

      {loading && !result && <div className="empty">Loading listings…</div>}

      <div className="product-grid">
        {items.map((x) => (
          <ProductCard
            item={x}
            onAddToCart={addToCart}
            onReport={(item) => nav(`/report/${item.id}`)}
            key={x.id}
          />
        ))}
      </div>

      {!loading && result && !items.length && (
        <div className="empty">No produce matches those filters. Try a different search.</div>
      )}

      {result && result.pages > 1 && (
        <div className="tabs" style={{ marginTop: 28, justifyContent: 'center' }}>
          <button onClick={() => update({ page: result.page - 1 })} disabled={result.page <= 1}>
            Previous
          </button>
          {Array.from({ length: result.pages }, (_, i) => i + 1).map((n) => (
            <button key={n} className={n === result.page ? 'active' : ''} onClick={() => update({ page: n })}>
              {n}
            </button>
          ))}
          <button onClick={() => update({ page: result.page + 1 })} disabled={result.page >= result.pages}>
            Next
          </button>
        </div>
      )}

      <p className="muted" style={{ marginTop: 24 }}>
        Looking for something specific? <Link className="inline-link" to="/how-it-works">See how ordering works</Link>
      </p>
    </main>
  );
}
