import { useEffect } from 'react';
import { CircleMarker, MapContainer, TileLayer, useMap, useMapEvents } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

// Nashik, Maharashtra — the centre of the seeded demo data.
const DEFAULT_CENTER: [number, number] = [19.9975, 73.7898];
const REGION_ZOOM = 6;
const PINNED_ZOOM = 11;

function ClickToPin({ onPick }: { onPick: (lat: number, lng: number) => void }) {
  useMapEvents({
    click(event) {
      onPick(event.latlng.lat, event.latlng.lng);
    },
  });
  return null;
}

/**
 * Keeps the view on the pin as it changes.
 *
 * MapContainer reads `center` only when it mounts, so dropping a pin elsewhere
 * — or clearing one — left the map showing wherever it started. This watches
 * the coordinates and calls setView, which is the only way to move an existing
 * map instance.
 */
function FollowPin({ lat, lng }: { lat: number | null; lng: number | null }) {
  const map = useMap();

  useEffect(() => {
    if (lat === null || lng === null) {
      map.setView(DEFAULT_CENTER, REGION_ZOOM);
      return;
    }
    map.setView([lat, lng], PINNED_ZOOM);
  }, [lat, lng, map]);

  return null;
}

export default function LocationPicker({
  lat,
  lng,
  onChange,
}: {
  lat: number | null;
  lng: number | null;
  onChange: (lat: number | null, lng: number | null) => void;
}) {
  // Direct narrowing rather than an aliased boolean. `lat !== null && lng !== null`
  // stored in a const then used inside JSX is exactly the case where
  // TypeScript's aliased-condition narrowing is least reliable.
  const pinned = lat !== null && lng !== null;
  const center: [number, number] = pinned ? [lat, lng] : DEFAULT_CENTER;

  return (
    <div>
      <div style={{ borderRadius: 7, overflow: 'hidden', border: '1px solid #d9e5d5' }}>
        <MapContainer
          center={center}
          zoom={pinned ? PINNED_ZOOM : REGION_ZOOM}
          scrollWheelZoom={false}
          style={{ height: 300, width: '100%' }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <ClickToPin onPick={(la, ln) => onChange(la, ln)} />
          <FollowPin lat={lat} lng={lng} />
          {/* CircleMarker, not Marker. Leaflet's default marker is a PNG
              resolved at runtime from a URL that bundlers mangle, so Marker
              renders invisibly under Vite without extra icon plumbing. */}
          {lat !== null && lng !== null && (
            <CircleMarker
              center={[lat, lng]}
              radius={11}
              pathOptions={{ color: '#23643e', weight: 3, fillColor: '#23643e', fillOpacity: 0.45 }}
            />
          )}
        </MapContainer>
      </div>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginTop: 8 }}>
        <span className="muted">
          {lat !== null && lng !== null
            ? `Pinned at ${lat.toFixed(4)}, ${lng.toFixed(4)}`
            : 'Optional — click the map to drop a pin.'}
        </span>
        {lat !== null && lng !== null && (
          <button type="button" className="text-button" onClick={() => onChange(null, null)}>
            Clear pin
          </button>
        )}
      </div>
    </div>
  );
}
