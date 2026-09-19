import { Link } from 'react-router-dom';
import { Sprout } from 'lucide-react';

export default function Footer() {
  return (
    <footer>
      <Link className="brand" to="/">
        <span>
          <Sprout size={19} />
        </span>
        FarmLink
      </Link>
      <p>Direct trade for a stronger food system.</p>
      <span>SIH26033 prototype</span>
    </footer>
  );
}
