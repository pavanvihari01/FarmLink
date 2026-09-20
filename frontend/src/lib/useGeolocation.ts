import { useCallback, useState } from 'react';

export type GeoPoint = { lat: number; lng: number };

export type GeoStatus = 'idle' | 'asking' | 'granted' | 'denied' | 'unsupported';

const STORAGE_KEY = 'farmlink.geo';

function readStored(): GeoPoint | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (typeof parsed?.lat === 'number' && typeof parsed?.lng === 'number') return parsed;
    return null;
  } catch {
    return null;
  }
}

/**
 * Browser geolocation, cached in localStorage so the permission prompt appears
 * once rather than on every visit to the marketplace.
 *
 * Nothing is requested on mount. The caller decides when to ask — in this app,
 * only when the buyer picks the "nearest" sort. Requesting on page load would
 * prompt people who never wanted distance sorting.
 */
export function useGeolocation() {
  const [point, setPoint] = useState<GeoPoint | null>(readStored);
  const [status, setStatus] = useState<GeoStatus>(readStored() ? 'granted' : 'idle');
  const [error, setError] = useState('');

  const request = useCallback(() => {
    if (!('geolocation' in navigator)) {
      setStatus('unsupported');
      setError('This browser cannot share your location.');
      return;
    }
    setStatus('asking');
    setError('');
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const next = { lat: position.coords.latitude, lng: position.coords.longitude };
        setPoint(next);
        setStatus('granted');
        try {
          localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
        } catch {
          // Storage blocked. The in-memory point still works for this session.
        }
      },
      () => {
        setStatus('denied');
        setError('Location was declined, so distance cannot be shown.');
      },
      { timeout: 10000, maximumAge: 5 * 60 * 1000 },
    );
  }, []);

  const clear = useCallback(() => {
    setPoint(null);
    setStatus('idle');
    setError('');
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      // Nothing to clean up if storage is unavailable.
    }
  }, []);

  return { point, status, error, request, clear };
}
