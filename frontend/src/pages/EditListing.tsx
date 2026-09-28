import { useEffect, useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from '../lib/api';
import LocationPicker from '../components/LocationPicker';
import type { Category, Listing, User } from '../types';

const UNITS = ['kg', 'g', 'dozen', 'piece', 'bunch', 'litre'];
const ACCEPTED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_IMAGE_MB = 10;

export default function EditListing({ user }: { user: User }) {
  const { listingId } = useParams();
  const nav = useNavigate();

  const [listing, setListing] = useState<Listing | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [removing, setRemoving] = useState(false);

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
    const id = Number(listingId);
    if (!id) {
      setError('That listing link is not valid.');
      return;
    }
    api.categories().then(setCategories).catch(() => undefined);
    api
      .listing(id)
      .then((x) => {
        if (x.farmer_id !== user.id) {
          setError('This is not your listing.');
          return;
        }
        setListing(x);
        setTitle(x.title);
        setDescription(x.description);
        setCategoryId(String(x.category_id));
        setPrice(String(x.price_per_unit));
        setUnit(x.unit);
        setQuantity(String(x.available_quantity));
        setLifespan(String(x.lifespan_hours));
        setOrganic(x.organic);
        setBulkAvailable(x.bulk_available);
        setLocationText(x.location);
        setLat(x.latitude);
        setLng(x.longitude);
        setImageUrl(x.image_url);
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'That listing could not be loaded.'));
  }, [listingId, user.id]);

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
    if (!Number.isFinite(quantityValue) || quantityValue < 0) return setError('Quantity cannot be negative.');
    if (!Number.isFinite(lifespanValue) || lifespanValue < 1 || lifespanValue > 720) {
      return setError('Useful life must be between 1 and 720 hours.');
    }
    if (!locationText.trim()) return setError('Add a location.');

    setBusy(true);
    try {
      const r = await api.updateListing(Number(listingId), {
        category_id: Number(categoryId),
        title: title.trim(),
        description: description.trim(),
        price_per_unit: priceValue,
        unit,
        available_quantity: quantityValue,
        lifespan_hours: lifespanValue,
        organic,
        bulk_available: bulkAvailable,
        location_text: locationText.trim(),
        latitude: lat ?? undefined,
        longitude: lng ?? undefined,
        image_url: imageUrl,
      });
      nav(`/listings/${r.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'That listing could not be saved.');
    } finally {
      setBusy(false);
    }
  };

  const remove = async (cancelOpenOrders = false) => {
    setError('');
    setRemoving(true);
    try {
      await api.deleteListing(Number(listingId), cancelOpenOrders);
      nav('/dashboard');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'That listing could not be removed.');
    } finally {
      setRemoving(false);
    }
  };

  if (error && !listing) {
    return (
      <main className="page">
        <div className="page-intro">
          <span className="eyebrow">Edit listing</span>
          <h1>Not available</h1>
          <p>{error}</p>
        </div>
        <Link className="button" to="/dashboard">
          Back to dashboard
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

  return (
    <main className="page">
      <div className="page-intro">
        <span className="eyebrow">Edit listing</span>
        <h1>{listing.title}</h1>
        <p>Buyers see freshness first, so be accurate about when this was harvested.</p>
      </div>

      {error && <p className="error">{error}</p>}

      <form className="auth" style={{ margin: 0, padding: 0, maxWidth: 620 }} onSubmit={submit}>
        <label>
          Title
          <input value={title} onChange={(e) => setTitle(e.target.value)} required />
        </label>

        <label>
          Description
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            style={{ padding: 12, border: '1px solid #cfdccb', borderRadius: 5, background: '#fff', font: 'inherit' }}
          />
        </label>

        <label>
          Category
          <select value={categoryId} onChange={(e) => setCategoryId(e.target.value)} required>
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
          <input type="number" min="0.01" step="0.01" value={price} onChange={(e) => setPrice(e.target.value)} required />
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
          Quantity still available
          <input type="number" min="0" step="0.1" value={quantity} onChange={(e) => setQuantity(e.target.value)} required />
        </label>

        <p className="muted" style={{ margin: 0 }}>
          This is what is left, not the original harvest. Orders already placed have taken their share out.
        </p>

        <label>
          Harvested at (optional)
          <input type="datetime-local" value={harvestTime} onChange={(e) => setHarvestTime(e.target.value)} />
        </label>

        <label>
          Expected lifespan (hours)
          <input type="number" min="1" max="720" value={lifespan} onChange={(e) => setLifespan(e.target.value)} required />
        </label>

        <p className="muted" style={{ margin: 0 }}>
          Remaining freshness: {listing.remaining_hours > 0 ? `${listing.remaining_hours} hours` : 'expired'}
        </p>

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
          <input value={locationText} onChange={(e) => setLocationText(e.target.value)} required />
        </label>

        <div>
          <span className="eyebrow">Pin on the map (optional)</span>
          <div style={{ marginTop: 10 }}>
            <LocationPicker lat={lat} lng={lng} onChange={(la, ln) => { setLat(la); setLng(ln); }} />
          </div>
        </div>

        <div>
          <span className="eyebrow">Photo</span>
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
              <img
                src={imageUrl}
                alt="Listing preview"
                style={{ width: 180, borderRadius: 7, border: '1px solid #e1e9de', display: 'block' }}
              />
            )}
            <p className="muted" style={{ margin: 0 }}>
              Replacing the photo removes the previous file. JPEG, PNG, or WebP up to {MAX_IMAGE_MB} MB.
            </p>
          </div>
        </div>

        <button className="button" type="submit" disabled={busy || uploading}>
          {busy ? 'Saving…' : 'Save changes'}
        </button>
      </form>

      <section className="section" style={{ padding: 0, marginTop: 40 }}>
        <div className="section-heading">
          <div>
            <span className="eyebrow">Danger zone</span>
            <h2>Remove this listing</h2>
          </div>
        </div>
        <div className="cart-summary" style={{ maxWidth: 620 }}>
          <p style={{ margin: 0 }}>
            The listing disappears from the marketplace. Orders already placed keep their history.
          </p>
          <p className="muted" style={{ margin: 0 }}>
            If anyone has an open order on this listing you will be asked to confirm cancelling it first. Their
            reserved stock goes back to you.
          </p>
          <button className="text-button" onClick={() => remove(false)} disabled={removing}>
            {removing ? 'Working…' : 'Remove listing'}
          </button>
          <button className="text-button" onClick={() => remove(true)} disabled={removing}>
            Remove and cancel open orders
          </button>
        </div>
      </section>
    </main>
  );
}
