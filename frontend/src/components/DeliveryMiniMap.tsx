import { CircleMarker, MapContainer, TileLayer } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

/**
 * A small read-only map showing where one order is going.
 *
 * Dragging and scroll zoom are off: this is a reference, not a tool. The buyer
 * is looking at where their food is headed, not planning a route.
 */
export default function DeliveryMiniMap({ lat, lng }: { lat: number; lng: number }) {
  return (
    <div style={{ borderRadius: 7, overflow: 'hidden', border: '1px solid #d9e5d5', marginTop: 8 }}>
      <MapContainer
        center={[lat, lng]}
        zoom={13}
        scrollWheelZoom={false}
        dragging={false}
        zoomControl={false}
        style={{ height: 170, width: '100%' }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <CircleMarker
          center={[lat, lng]}
          radius={10}
          pathOptions={{ color: '#23643e', weight: 3, fillColor: '#d6eb5f', fillOpacity: 0.9 }}
        />
      </MapContainer>
    </div>
  );
}
