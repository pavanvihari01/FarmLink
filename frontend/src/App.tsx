import { useEffect, useState } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { api } from './lib/api';
import { CartProvider } from './context/CartContext';
import type { Listing, User } from './types';
import Header from './components/Header';
import Footer from './components/Footer';
import Home from './pages/Home';
import Marketplace from './pages/Marketplace';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import HowItWorks from './pages/HowItWorks';
import Cart from './pages/Cart';
import Checkout from './pages/Checkout';
import Orders from './pages/Orders';
import Profile from './pages/Profile';
import ReportPage from './pages/Report';
import CreateListing from './pages/CreateListing';
import EditListing from './pages/EditListing';
import Admin from './pages/Admin';
import ListingDetail from './pages/ListingDetail';
import Subscriptions from './pages/Subscriptions';
import Deliveries from './pages/Deliveries';
import Forecast from './pages/Forecast';

function App() {
  const [featured, setFeatured] = useState<Listing[]>([]);
  // The same response that fills `featured` also carries the total number of
  // live listings. Taking it here avoids a second request, and avoids the home
  // page showing a hardcoded figure that nothing backs.
  const [liveCount, setLiveCount] = useState<number | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [notice, setNotice] = useState('');

  useEffect(() => {
    api
      .listings({ page_size: 4 })
      .then((r) => {
        setFeatured(r.items);
        setLiveCount(r.total);
      })
      .catch(() => setNotice('The API is not running yet. Start the backend to load marketplace data.'));
    if (localStorage.token) api.me().then(setUser).catch(() => localStorage.removeItem('token'));
  }, []);

  return (
    <CartProvider>
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
        <Route path="/" element={<Home items={featured} liveCount={liveCount} />} />
        <Route path="/marketplace" element={<Marketplace />} />
        <Route path="/listings/:listingId" element={<ListingDetail user={user} />} />
        <Route
          path="/listings/:listingId/edit"
          element={
            user && user.role === 'farmer' ? <EditListing user={user} /> : <Navigate to="/dashboard" />
          }
        />
        <Route path="/how-it-works" element={<HowItWorks />} />
        <Route path="/cart" element={<Cart user={user} />} />
        <Route path="/report/:listingId" element={<ReportPage user={user} />} />
        <Route path="/login" element={<Login onLogin={setUser} />} />
        <Route path="/register" element={<Register onLogin={setUser} />} />
        <Route path="/checkout" element={user ? <Checkout /> : <Navigate to="/login" />} />
        <Route path="/orders" element={user ? <Orders user={user} /> : <Navigate to="/login" />} />
        <Route
          path="/subscriptions"
          element={user ? <Subscriptions user={user} /> : <Navigate to="/login" />}
        />
        <Route
          path="/deliveries"
          element={user && user.role === 'farmer' ? <Deliveries user={user} /> : <Navigate to="/dashboard" />}
        />
        <Route
          path="/forecast"
          element={user && user.role === 'farmer' ? <Forecast user={user} /> : <Navigate to="/dashboard" />}
        />
        <Route
          path="/profile"
          element={user ? <Profile user={user} onUserUpdate={setUser} /> : <Navigate to="/login" />}
        />
        <Route
          path="/listings/new"
          element={
            user && user.role === 'farmer' ? <CreateListing user={user} /> : <Navigate to="/dashboard" />
          }
        />
        <Route
          path="/admin"
          element={user && user.role === 'admin' ? <Admin user={user} /> : <Navigate to="/dashboard" />}
        />
        <Route
          path="/dashboard"
          element={user ? <Dashboard user={user} items={featured} /> : <Navigate to="/login" />}
        />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
      <Footer />
    </CartProvider>
  );
}

export default App;
