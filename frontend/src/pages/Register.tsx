import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';

export default function Register() {
  return (
    <main className="auth">
      <span className="eyebrow">Get started</span>
      <h1>Build a shorter path from farm to table.</h1>
      <p>
        Create a farmer, consumer, or bulk-buyer account. Your first listings and orders can be made in minutes.
      </p>
      <Link to="/login" className="button">
        Choose your role <ArrowRight size={18} />
      </Link>
    </main>
  );
}
