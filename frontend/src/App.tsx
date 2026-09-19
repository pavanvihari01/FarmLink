import { useEffect, useState } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { api } from './lib/api';
import type { Listing, User } from './types';
import Header from './components/Header';
import Footer from './components/Footer';
import Home from './pages/Home';
import Marketplace from './pages/Marketplace';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import HowItWorks from './pages/HowItWorks';

function App() {
  const [items, setItems] = useState<Listing[]>([]);
  const [user, setUser] = useState<User | null>(null);
  const [notice, setNotice] = useState('');

  useEffect(() => {
    api
      .listings()
      .then(setItems)
      .catch(() => setNotice('The API is not running yet. Start the backend to load marketplace data.'));
    if (localStorage.token) api.me().then(setUser).catch(() => localStorage.removeItem('token'));
  }, []);

  const order = (i: Listing) => {
    if (!user) {
      setNotice('Sign in as a buyer to place an order.');
      return;
    }
    api
      .order(i.id, 1)
      .then(() => setNotice(`Order request sent to ${i.farmer_name}.`))
      .catch((e: unknown) => setNotice(e instanceof Error ? e.message : 'Something went wrong'));
  };

  return (
    <>
      <Header
        user={user}
        onLogout={() => {
          localStorage.removeItem('token');
          setUser(null);
        }}
      />
      {notice && (
        <div className="toast">
          {notice}
          <button onClick={() => setNotice('')} aria-label="Dismiss">
            x
          </button>
        </div>
      )}
      <Routes>
        <Route path="/" element={<Home items={items} />} />
        <Route path="/marketplace" element={<Marketplace items={items} onOrder={order} />} />
        <Route path="/how-it-works" element={<HowItWorks />} />
        <Route path="/login" element={<Login onLogin={setUser} />} />
        <Route path="/register" element={<Register />} />
        <Route
          path="/dashboard"
          element={user ? <Dashboard user={user} items={items} /> : <Navigate to="/login" />}
        />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
      <Footer />
    </>
  );
}

export default App;
