import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Menu, Sprout, X } from 'lucide-react';
import type { User } from '../types';

export default function Header({ user, onLogout }: { user: User | null; onLogout: () => void }) {
  const [open, setOpen] = useState(false);

  return (
    <header>
      <Link className="brand" to="/">
        <span>
          <Sprout size={23} />
        </span>
        FarmLink
      </Link>
      <button className="menu-button" aria-label="Open navigation" onClick={() => setOpen(!open)}>
        {open ? <X /> : <Menu />}
      </button>
      <nav className={open ? 'open' : ''}>
        <Link to="/marketplace">Marketplace</Link>
        <Link to="/how-it-works">How it works</Link>
        {user ? (
          <>
            <Link to="/dashboard">Dashboard</Link>
            <button className="text-button" onClick={onLogout}>
              Sign out
            </button>
          </>
        ) : (
          <Link className="button small" to="/login">
            Sign in
          </Link>
        )}
      </nav>
    </header>
  );
}
