import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, ShoppingBasket } from 'lucide-react';
import { api } from '../lib/api';
import { demoAccounts } from '../lib/constants';
import type { User } from '../types';

export default function Login({ onLogin }: { onLogin: (u: User) => void }) {
  const [error, setError] = useState('');
  const nav = useNavigate();

  const login = async (email: string, password: string) => {
    try {
      const r = await api.login(email, password);
      localStorage.token = r.access_token;
      onLogin(r.user);
      nav('/dashboard');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to sign in');
    }
  };

  return (
    <main className="auth">
      <div>
        <span className="eyebrow">Welcome back</span>
        <h1>Sign in to FarmLink</h1>
        <p>Use a demo role to explore the complete marketplace immediately.</p>
      </div>
      <div className="demo-list">
        {demoAccounts.map((a) => (
          <button key={a.email} onClick={() => login(a.email, a.password)}>
            <span>
              <ShoppingBasket size={18} />
            </span>
            <b>{a.label}</b>
            <small>Open demo</small>
          </button>
        ))}
      </div>
      <div className="divider">
        <span>or sign in manually</span>
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const d = new FormData(e.currentTarget);
          login(String(d.get('email')), String(d.get('password')));
        }}
      >
        <label>
          Email
          <input name="email" type="email" required />
        </label>
        <label>
          Password
          <input name="password" type="password" required />
        </label>
        {error && <p className="error">{error}</p>}
        <button className="button" type="submit">
          Sign in <ArrowRight size={18} />
        </button>
      </form>
      <p>
        New to FarmLink? <Link to="/register">Create an account</Link>
      </p>
    </main>
  );
}
