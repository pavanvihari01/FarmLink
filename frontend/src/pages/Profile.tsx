import { useEffect, useState, type FormEvent } from 'react';
import { Pencil, Trash2 } from 'lucide-react';
import { api, type AddressUpdatePayload } from '../lib/api';
import LocationPicker from '../components/LocationPicker';
import type { Address, PaymentMethod, User } from '../types';

export default function Profile({
  user,
  onUserUpdate,
}: {
  user: User;
  onUserUpdate: (u: User) => void;
}) {
  const [addresses, setAddresses] = useState<Address[]>([]);
  const [methods, setMethods] = useState<PaymentMethod[]>([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const [name, setName] = useState(user.name);
  const [email, setEmail] = useState(user.email);
  const [phone, setPhone] = useState(user.phone ?? '');
  const [savingProfile, setSavingProfile] = useState(false);

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [savingPassword, setSavingPassword] = useState(false);

  // Which address is being edited. null means the add form is showing.
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editLabel, setEditLabel] = useState('');
  const [editLine1, setEditLine1] = useState('');
  const [editLine2, setEditLine2] = useState('');
  const [editCity, setEditCity] = useState('');
  const [editState, setEditState] = useState('');
  const [editPincode, setEditPincode] = useState('');
  const [editPhone, setEditPhone] = useState('');
  const [editLat, setEditLat] = useState<number | null>(null);
  const [editLng, setEditLng] = useState<number | null>(null);

  const [newLat, setNewLat] = useState<number | null>(null);
  const [newLng, setNewLng] = useState<number | null>(null);

  const load = () => {
    api.addresses().then(setAddresses).catch(() => setError('Unable to load addresses'));
    api.paymentMethods().then(setMethods).catch(() => setError('Unable to load payment methods'));
  };

  useEffect(() => {
    load();
  }, []);

  const saveProfile = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    setNotice('');
    if (!name.trim()) {
      setError('Name cannot be empty.');
      return;
    }
    setSavingProfile(true);
    try {
      const updated = await api.updateProfile({
        name: name.trim(),
        email: email.trim(),
        // An empty string clears the phone. The server treats None as
        // "unchanged" and "" as "remove it".
        phone: phone.trim(),
      });
      onUserUpdate(updated);
      setName(updated.name);
      setEmail(updated.email);
      setPhone(updated.phone ?? '');
      setNotice('Profile updated.');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to save your profile');
    } finally {
      setSavingProfile(false);
    }
  };

  const savePassword = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    setNotice('');
    setSavingPassword(true);
    try {
      await api.changePassword(currentPassword, newPassword);
      setCurrentPassword('');
      setNewPassword('');
      setNotice('Password changed. Devices already signed in stay signed in until their session expires.');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to change your password');
    } finally {
      setSavingPassword(false);
    }
  };

  const startEditing = (a: Address) => {
    setEditingId(a.id);
    setEditLabel(a.label);
    setEditLine1(a.line1);
    setEditLine2(a.line2 ?? '');
    setEditCity(a.city);
    setEditState(a.state);
    setEditPincode(a.pincode);
    setEditPhone(a.phone ?? '');
    setEditLat(a.latitude ?? null);
    setEditLng(a.longitude ?? null);
    setNotice('');
    setError('');
  };

  const cancelEditing = () => setEditingId(null);

  const saveAddress = async () => {
    if (editingId === null) return;
    setError('');
    setNotice('');
    const patch: AddressUpdatePayload = {
      label: editLabel.trim(),
      line1: editLine1.trim(),
      line2: editLine2.trim(),
      city: editCity.trim(),
      state: editState.trim(),
      pincode: editPincode.trim(),
      phone: editPhone.trim(),
      // null clears the pin; the API treats an explicit null as "remove".
      latitude: editLat,
      longitude: editLng,
    };
    try {
      await api.updateAddress(editingId, patch);
      setEditingId(null);
      load();
      setNotice('Address updated.');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to save that address');
    }
  };

  const makeDefault = async (id: number) => {
    setError('');
    try {
      await api.updateAddress(id, { is_default: true });
      load();
      setNotice('Default address changed.');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to change the default');
    }
  };

  const addAddress = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const d = new FormData(form);
    setError('');
    try {
      await api.createAddress({
        label: String(d.get('label')),
        line1: String(d.get('line1')),
        line2: String(d.get('line2')) || undefined,
        city: String(d.get('city')),
        state: String(d.get('state')),
        pincode: String(d.get('pincode')),
        phone: String(d.get('phone')) || undefined,
        latitude: newLat ?? undefined,
        longitude: newLng ?? undefined,
      });
      form.reset();
      setNewLat(null);
      setNewLng(null);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to save that address');
    }
  };

  const addMethod = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const d = new FormData(form);
    const type = String(d.get('method_type')) as 'upi' | 'card' | 'cod';
    setError('');
    try {
      await api.createPaymentMethod({
        label: String(d.get('label')),
        method_type: type,
        last4: type === 'card' ? String(d.get('last4')) : undefined,
      });
      form.reset();
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to save that payment method');
    }
  };

  return (
    <main className="page">
      <div className="page-intro">
        <span className="eyebrow">Profile</span>
        <h1>{user.name}</h1>
        <p>
          {user.email} · {user.role}
        </p>
      </div>

      {error && <p className="error">{error}</p>}
      {notice && <p className="result-banner">{notice}</p>}

      <section className="section" style={{ padding: 0, marginBottom: 40 }}>
        <div className="section-heading">
          <div>
            <span className="eyebrow">Your details</span>
            <h2>Account</h2>
          </div>
        </div>

        <form className="auth" style={{ margin: 0, padding: 0, maxWidth: 520 }} onSubmit={saveProfile}>
          <label>
            Full name
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <label>
            Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label>
            Phone
            <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="Optional" />
          </label>
          <button className="button" type="submit" disabled={savingProfile}>
            {savingProfile ? 'Saving…' : 'Save changes'}
          </button>
        </form>
      </section>

      <section className="section" style={{ padding: 0, marginBottom: 40 }}>
        <div className="section-heading">
          <div>
            <span className="eyebrow">Security</span>
            <h2>Change password</h2>
          </div>
        </div>

        <form className="auth" style={{ margin: 0, padding: 0, maxWidth: 520 }} onSubmit={savePassword}>
          <label>
            Current password
            <input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </label>
          <label>
            New password
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              autoComplete="new-password"
              minLength={8}
              required
            />
          </label>
          <button className="button" type="submit" disabled={savingPassword}>
            {savingPassword ? 'Changing…' : 'Change password'}
          </button>
        </form>
      </section>

      <section className="section" style={{ padding: 0, marginBottom: 40 }}>
        <div className="section-heading">
          <div>
            <span className="eyebrow">Delivery</span>
            <h2>Saved addresses</h2>
          </div>
        </div>

        <div style={{ display: 'grid', gap: 12, marginBottom: 20 }}>
          {!addresses.length && <div className="empty">No saved addresses yet.</div>}
          {addresses.map((a) =>
            editingId === a.id ? (
              <div className="order-card" key={a.id}>
                <div className="order-head">
                  <strong>Editing {a.label}</strong>
                </div>
                <div className="auth" style={{ margin: 0, padding: 0, maxWidth: 520 }}>
                  <label>
                    Label
                    <input value={editLabel} onChange={(e) => setEditLabel(e.target.value)} />
                  </label>
                  <label>
                    Address line 1
                    <input value={editLine1} onChange={(e) => setEditLine1(e.target.value)} />
                  </label>
                  <label>
                    Address line 2
                    <input value={editLine2} onChange={(e) => setEditLine2(e.target.value)} />
                  </label>
                  <label>
                    City
                    <input value={editCity} onChange={(e) => setEditCity(e.target.value)} />
                  </label>
                  <label>
                    State
                    <input value={editState} onChange={(e) => setEditState(e.target.value)} />
                  </label>
                  <label>
                    PIN code
                    <input value={editPincode} onChange={(e) => setEditPincode(e.target.value)} />
                  </label>
                  <label>
                    Phone
                    <input value={editPhone} onChange={(e) => setEditPhone(e.target.value)} />
                  </label>
                </div>
                <div style={{ marginTop: 12 }}>
                  <span className="eyebrow">Pin on the map (optional)</span>
                  <div style={{ marginTop: 10 }}>
                    <LocationPicker lat={editLat} lng={editLng} onChange={(la, ln) => { setEditLat(la); setEditLng(ln); }} />
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 12, marginTop: 12 }}>
                  <button className="button small" onClick={saveAddress}>
                    Save
                  </button>
                  <button className="text-button" onClick={cancelEditing}>
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div className="order-card" key={a.id}>
                <div className="order-head">
                  <strong>
                    {a.label}
                    {a.is_default && <span className="badge fresh" style={{ marginLeft: 8 }}>Default</span>}
                  </strong>
                  <div style={{ display: 'flex', gap: 10 }}>
                    <button className="text-button" onClick={() => startEditing(a)} aria-label={`Edit ${a.label}`}>
                      <Pencil size={17} />
                    </button>
                    <button
                      className="text-button"
                      onClick={() => api.deleteAddress(a.id).then(load)}
                      aria-label={`Delete ${a.label}`}
                    >
                      <Trash2 size={17} />
                    </button>
                  </div>
                </div>
                <span className="muted">
                  {[a.line1, a.line2, a.city, a.state, a.pincode].filter(Boolean).join(', ')}
                </span>
                <span className="muted">
                  {a.latitude !== null && a.latitude !== undefined
                    ? `Pinned at ${a.latitude.toFixed(4)}, ${a.longitude?.toFixed(4)}`
                    : 'Not pinned — cannot be placed on a delivery route'}
                </span>
                {!a.is_default && (
                  <button className="text-button" onClick={() => makeDefault(a.id)}>
                    Make this the default
                  </button>
                )}
              </div>
            )
          )}
        </div>

        <form className="auth" style={{ margin: 0, padding: 0, maxWidth: 560 }} onSubmit={addAddress}>
          <h2 style={{ fontSize: '1rem', margin: 0 }}>Add an address</h2>
          <label>
            Label
            <input name="label" required placeholder="Home" />
          </label>
          <label>
            Address line 1
            <input name="line1" required />
          </label>
          <label>
            Address line 2
            <input name="line2" />
          </label>
          <label>
            City
            <input name="city" required />
          </label>
          <label>
            State
            <input name="state" required />
          </label>
          <label>
            PIN code
            <input name="pincode" required />
          </label>
          <label>
            Phone
            <input name="phone" />
          </label>

          <div>
            <span className="eyebrow">Pin on the map (optional)</span>
            <p className="muted" style={{ margin: '4px 0 10px' }}>
              Without a pin this address still works for pickup ordering, but a farmer cannot route a
              delivery to it.
            </p>
            <LocationPicker lat={newLat} lng={newLng} onChange={(la, ln) => { setNewLat(la); setNewLng(ln); }} />
          </div>

          <button className="button" type="submit">
            Save address
          </button>
        </form>
      </section>

      <section className="section" style={{ padding: 0 }}>
        <div className="section-heading">
          <div>
            <span className="eyebrow">Payment</span>
            <h2>Payment methods</h2>
          </div>
        </div>
        <div style={{ display: 'grid', gap: 12, marginBottom: 20 }}>
          {!methods.length && <div className="empty">No saved payment methods yet.</div>}
          {methods.map((m) => (
            <div className="order-card" key={m.id}>
              <div className="order-head">
                <strong>
                  {m.label}
                  {m.is_default && <span className="badge fresh" style={{ marginLeft: 8 }}>Default</span>}
                </strong>
                <button
                  className="text-button"
                  onClick={() => api.deletePaymentMethod(m.id).then(load)}
                  aria-label={`Delete ${m.label}`}
                >
                  <Trash2 size={17} />
                </button>
              </div>
              <span className="muted">
                {m.method_type.toUpperCase()}
                {m.last4 ? ` ····${m.last4}` : ''}
              </span>
            </div>
          ))}
        </div>

        <form className="auth" style={{ margin: 0, padding: 0, maxWidth: 520 }} onSubmit={addMethod}>
          <h2 style={{ fontSize: '1rem', margin: 0 }}>Add a payment method</h2>
          <label>
            Label
            <input name="label" required placeholder="UPI me@bank" />
          </label>
          <label>
            Type
            <select name="method_type" required defaultValue="upi">
              <option value="upi">UPI</option>
              <option value="card">Card</option>
              <option value="cod">Cash on delivery</option>
            </select>
          </label>
          <label>
            Last 4 digits (cards only)
            <input name="last4" maxLength={4} inputMode="numeric" />
          </label>
          <p className="muted" style={{ margin: 0 }}>
            Nothing sensitive is stored. Cards keep a label and four digits for display only.
          </p>
          <button className="button" type="submit">
            Save payment method
          </button>
        </form>
      </section>
    </main>
  );
}
