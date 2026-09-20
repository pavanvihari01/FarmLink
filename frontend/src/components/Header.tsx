import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Menu, ShoppingCart, Sprout, X } from 'lucide-react';
import { useCart } from '../context/CartContext';
import LanguageTranslator from './LanguageTranslator';
import type { User } from '../types';

export default function Header({ user, onLogout }: { user: User | null; onLogout: () => void }) {
  const [open, setOpen] = useState(false);
  const { count } = useCart();

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
      <LanguageTranslator />
        <Link to="/marketplace">Marketplace</Link>
        <Link to="/how-it-works">How it works</Link>
        {user ? (
          <>
            <Link to="/dashboard">Dashboard</Link>
            {user.role === 'farmer' && <Link to="/listings/new">Sell</Link>}
            {user.role === 'farmer' && <Link to="/deliveries">Deliveries</Link>}
            {user.role === 'farmer' && <Link to="/forecast">Forecast</Link>}
            {user.role === 'admin' && <Link to="/admin">Admin</Link>}
            <Link to="/orders">Orders</Link>
            {user.role !== 'admin' && <Link to="/subscriptions">Subscriptions</Link>}
            <Link to="/profile">Profile</Link>
            <Link to="/cart" className="cart-link" aria-label={`Cart, ${count} items`}>
              <ShoppingCart size={20} />
              {count > 0 && <span className="cart-count">{count}</span>}
            </Link>
            <button className="text-button" onClick={onLogout}>
              Sign out
            </button>
          </>
        ) : (
          <>
            <Link to="/cart" className="cart-link" aria-label={`Cart, ${count} items`}>
              <ShoppingCart size={20} />
              {count > 0 && <span className="cart-count">{count}</span>}
            </Link>
            <Link className="button small" to="/login">
              Sign in
            </Link>
          </>
        )}
      </nav>
    </header>
  );
}

