import { useEffect, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import LocationPicker from '../components/LocationPicker';
import type { Category, ReportAgainstMe, User } from '../types';

const UNITS = ['kg', 'g', 'dozen', 'piece', 'bunch', 'litre'];
const ACCEPTED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_IMAGE_MB = 10;

export default function CreateListing({ user }: { user: User }) {
  const [categories, setCategories] = useState<Category[]>([]);
  const [lock, setLock] = useState<ReportAgainstMe | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [createdId, setCreatedId] = useState<number | null>(null);
  const [createdLifespan, setCreatedLifespan] = useState<number | null>(null);

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [price, setPrice] = useState('');
  const [unit, setUnit] = useState('kg');
  const [quantity, setQuantity] = useState('');
  const [harvestTime, setHarvestTime] = useState('');
  const [lifespan, setLifespan] = useState('');
  const [organic, setOrganic] = useState(false);
  const [bulkAvailable, setBulkAvailable] = useState(false);
  const [locationText, setLocationText] = useState('');
  const [lat, setLat] = useState<number | null>(null);
  const [lng, setLng] = useState<number | null>(null);
  const [imageUrl, setImageUrl] = useState('');
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    api.categories().then(setCategories).catch(() => setError('Unable to load categories.'));
    // A failure here leaves the field editable. That is the safe default: the
    // server enforces the lock regardless of what this page shows.
    api.reportsAgainstMe().then(setLock).catch(() => setLock(null));
  }, []);

  const locked = lock?.locked ?? false;

  const onCategoryChange = (value: string) => {
    setCategoryId(value);
    const category = categories.find((c) => String(c.id) === value);
    // Adopt the category's default. When locked this is not just a
    // convenience — the server will store exactly this number.
    if (category) setLifespan(String(category.default_lifespan_hours));
  };

  const pickImage = async (file: File) => {
    if (!ACCEPTED_IMAGE_TYPES.includes(file.type)) {
      setError('Images must be JPEG, PNG, or WebP.');
      return;
    }
    if (file.size > MAX_IMAGE_MB * 1024 * 1024) {
      setError(`That image is ${(file.size / 1024 / 1024).toFixed(1)} MB. The limit is ${MAX_IMAGE_MB} MB.`);
      return;
    }
    setUploading(true);
    setError('');
    try {
      const r = await api.uploadImage(file);
      setImageUrl(r.url);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'That image could not be uploaded.');
    } finally {
      setUploading(false);
    }
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');

    const priceValue = Number(price);
    const quantityValue = Number(quantity);
    const lifespanValue = Number(lifespan);

    if (!title.trim()) return setError('Give the listing a title.');
    if (!categoryId) return setError('Choose a category.');
    if (!Number.isFinite(priceValue) || priceValue <= 0) return setError('Price must be greater than zero.');
    if (!Number.isFinite(quantityValue) || quantityValue <= 0) return setError('Quantity must be greater than zero.');
    if (!Number.isFinite(lifespanValue) || lifespanValue < 1 || lifespanValue > 720) {
      return setError('Useful life must be between 1 and 720 hours.');
    }
    if (!locationText.trim()) return setError('Add a location so buyers know where this is.');

    if (harvestTime && new Date(harvestTime).getTime() > Date.now()) {
      return setError('Harvest time cannot be in the future.');
    }

    setBusy(true);
    try {
      const result = await api.createListing({
        category_id: Number(categoryId),
        title: title.trim(),
        description: description.trim(),
        price_per_unit: priceValue,
        unit,
        available_quantity: quantityValue,
        harvest_time: harvestTime ? new Date(harvestTime).toISOString() : undefined,
        lifespan_hours: lifespanValue,
        organic,
        bulk_available: bulkAvailable,
        location_text: locationText.trim(),
        latitude: lat ?? undefined,
        longitude: lng ?? undefined,
        image_url: imageUrl || undefined,
      });
      setCreatedId(result.id);
      setCreatedLifespan(result.lifespan_hours);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'That listing could not be saved.');
    } finally {
      setBusy(false);
    }
  };

  if (createdId !== null) {
    // The server may have replaced the lifespan we sent, so report what was
    // actually stored rather than what the form showed.
    const overridden = createdLifespan !== null && String(createdLifespan) !== lifespan;
    return (
      <main className="page">
        <div className="page-intro">
          <span className="eyebrow">Listing created</span>
          <h1>{title}</h1>
          <p>It is live on the marketplace now.</p>
        </div>
        <div className="result-banner">
          <p>
            Useful life stored as <b>{createdLifespan} hours</b>.
          </p>
          {overridden && (
            <p className="muted" style={{ marginTop: 6 }}>
              Your account has enough reports against it that the lifespan is fixed to the category default.
            </p>
          )}
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <Link className="button" to="/marketplace">
            See it on the marketplace
          </Link>
          <Link className="link-button" to="/dashboard" style={{ color: '#23643e' }}>
            Back to dashboard
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="page">
      <div className="page-intro">
        <span className="eyebrow">New listing</span>
        <h1>What are you selling?</h1>
        <p>Buyers see freshness first, so be accurate about when this was harvested.</p>
      </div>

      {error && <p className="error">{error}</p>}

      <form className="auth" style={{ margin: 0, padding: 0, maxWidth: 620 }} onSubmit={submit}>
        <label>
          Title
          <input value={title} onChange={(e) => setTitle(e.target.value)} required placeholder="Vine-ripe tomatoes" />
        </label>

        <label>
          Description
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            placeholder="How it was grown, what to expect."
            style={{ padding: 12, border: '1px solid #cfdccb', borderRadius: 5, background: '#fff', font: 'inherit' }}
          />
        </label>

        <label>
          Category
          <select value={categoryId} onChange={(e) => onCategoryChange(e.target.value)} required>
            <option value="">Choose a category</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>

        <label>
          Price per unit (Rs)
          <input
            type="number"
            min="0.01"
            step="0.01"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            required
          />
        </label>

        <label>
          Unit
          <select value={unit} onChange={(e) => setUnit(e.target.value)}>
            {UNITS.map((u) => (
              <option key={u} value={u}>
                {u}
              </option>
            ))}
          </select>
        </label>

        <label>
          Quantity available
          <input
            type="number"
            min="0.1"
            step="0.1"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            required
          />
        </label>

        <label>
          Harvested at (optional)
          <input type="datetime-local" value={harvestTime} onChange={(e) => setHarvestTime(e.target.value)} />
        </label>

        <label>
          Useful life (hours)
          <input
            type="number"
            min="1"
            max="720"
            value={lifespan}
            onChange={(e) => setLifespan(e.target.value)}
            disabled={locked}
            required
          />
        </label>

        {locked && lock && (
          <p className="muted" style={{ margin: 0 }}>
            Locked to the category default. {lock.count} reports have been filed against your listings, which is at
            or above the threshold of {lock.threshold}. The server enforces this — the value above is what will be
            stored.
          </p>
        )}

        <div style={{ display: 'flex', gap: 20 }}>
          <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontWeight: 400 }}>
            <input type="checkbox" checked={organic} onChange={(e) => setOrganic(e.target.checked)} />
            Grown organically
          </label>
          <label style={{ display: 'flex', gap: 8, alignItems: 'center', fontWeight: 400 }}>
            <input type="checkbox" checked={bulkAvailable} onChange={(e) => setBulkAvailable(e.target.checked)} />
            Available in bulk
          </label>
        </div>

        <label>
          Location
          <input
            value={locationText}
            onChange={(e) => setLocationText(e.target.value)}
            required
            placeholder="Nashik, Maharashtra"
          />
        </label>

        <div>
          <span className="eyebrow">Pin on the map (optional)</span>
          <div style={{ marginTop: 10 }}>
            <LocationPicker lat={lat} lng={lng} onChange={(la, ln) => { setLat(la); setLng(ln); }} />
          </div>
        </div>

        <div>
          <span className="eyebrow">Photo (optional)</span>
          <div style={{ marginTop: 10, display: 'grid', gap: 10 }}>
            <input
              type="file"
              accept={ACCEPTED_IMAGE_TYPES.join(',')}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) pickImage(file);
              }}
            />
            {uploading && <p className="muted">Uploading…</p>}
            {imageUrl && !uploading && (
              <div>
                <img
                  src={imageUrl}
                  alt="Listing preview"
                  style={{ width: 180, borderRadius: 7, border: '1px solid #e1e9de', display: 'block' }}
                />
                <button type="button" className="text-button" style={{ marginTop: 6 }} onClick={() => setImageUrl('')}>
                  Remove photo
                </button>
              </div>
            )}
            <p className="muted" style={{ margin: 0 }}>
              JPEG, PNG, or WebP up to {MAX_IMAGE_MB} MB. Without one, the default marketplace image is used.
            </p>
          </div>
        </div>

        <button className="button" type="submit" disabled={busy || uploading}>
          {busy ? 'Publishing…' : 'Publish listing'}
        </button>
      </form>
    </main>
  );
}
