import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from '../lib/api';
import type { Listing, ReportReason, User } from '../types';

const REASONS: { value: ReportReason; label: string; hint: string }[] = [
  { value: 'fake_lifespan', label: 'The freshness claim looks wrong', hint: 'The listed lifespan does not match what arrived.' },
  { value: 'wrong_quantity', label: 'The quantity did not match', hint: 'Less produce arrived than was ordered.' },
  { value: 'bad_quality', label: 'The produce quality was poor', hint: 'Damaged, spoiled, or not as described.' },
  { value: 'no_show', label: 'The farmer never delivered', hint: 'The order was accepted but nothing arrived.' },
  { value: 'other', label: 'Something else', hint: 'Describe it below.' },
];

export default function ReportPage({ user }: { user: User | null }) {
  const { listingId } = useParams();
  const nav = useNavigate();
  const [listing, setListing] = useState<Listing | null>(null);
  const [reason, setReason] = useState<ReportReason>('fake_lifespan');
  const [details, setDetails] = useState('');
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const id = Number(listingId);
    if (!id) {
      setError('That listing link is not valid.');
      return;
    }
    api
      .listing(id)
      .then(setListing)
      .catch(() => setError('That listing could not be found.'));
  }, [listingId]);

  if (!user) {
    return (
      <main className="page">
        <div className="page-intro">
          <span className="eyebrow">Report a listing</span>
          <h1>Sign in to report</h1>
          <p>Reports are tied to an account so farmers can see who raised an issue.</p>
        </div>
        <Link className="button" to="/login">
          Sign in
        </Link>
      </main>
    );
  }

  if (done) {
    return (
      <main className="page">
        <div className="page-intro">
          <span className="eyebrow">Report received</span>
          <h1>Thanks — we have logged it</h1>
          <p>
            You reported <b>{listing?.title}</b>. A repeated pattern of reports against the same farmer is what
            unlocks moderation, so this contributes to that count.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          <Link className="button" to="/marketplace">
            Back to marketplace
          </Link>
          <Link className="link-button" to="/orders" style={{ color: '#23643e' }}>
            View my orders
          </Link>
        </div>
      </main>
    );
  }

  const submit = async () => {
    if (!listing) return;
    setBusy(true);
    setError('');
    try {
      await api.fileReport({ listing_id: listing.id, reason, details: details.trim() || undefined });
      setDone(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'That report could not be filed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="page">
      <div className="page-intro">
        <span className="eyebrow">Report a listing</span>
        <h1>{listing ? listing.title : 'Loading…'}</h1>
        {listing && <p>Sold by {listing.farmer_name}</p>}
      </div>

      {error && <p className="error">{error}</p>}

      {listing && (
        <div className="cart-summary" style={{ maxWidth: 620 }}>
          <div>
            <span className="eyebrow">What went wrong</span>
            <div style={{ display: 'grid', gap: 10, marginTop: 10 }}>
              {REASONS.map((r) => (
                <label key={r.value} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', fontWeight: 400 }}>
                  <input
                    type="radio"
                    name="reason"
                    checked={reason === r.value}
                    onChange={() => setReason(r.value)}
                    style={{ marginTop: 4 }}
                  />
                  <span>
                    <b>{r.label}</b>
                    <br />
                    <span className="muted">{r.hint}</span>
                  </span>
                </label>
              ))}
            </div>
          </div>

          <label className="v-label" style={{ display: 'grid', gap: 6, fontWeight: 600 }}>
            Anything else? (optional)
            <textarea
              value={details}
              onChange={(e) => setDetails(e.target.value)}
              maxLength={2000}
              rows={4}
              placeholder="Add any detail that would help someone review this."
              style={{ padding: 12, border: '1px solid #cfdccb', borderRadius: 5, background: '#fff', font: 'inherit' }}
            />
          </label>

          <p className="muted" style={{ margin: 0 }}>
            One report per listing per account. You have not reported this listing before.
          </p>

          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <button className="button" onClick={submit} disabled={busy}>
              {busy ? 'Filing…' : 'File report'}
            </button>
            <button className="text-button" onClick={() => nav(-1)}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </main>
  );
}
