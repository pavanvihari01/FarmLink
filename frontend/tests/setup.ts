/// <reference types="vitest" />
import '@testing-library/jest-dom/vitest';
import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';
import { createElement } from 'react';

// react-leaflet drives real map tiles through Leaflet, which needs layout APIs
// jsdom does not implement. Every component the app imports must be stubbed:
// a missing export throws "[vitest] No export is defined on the mock", which
// surfaces as a page-level failure rather than a missing-stub one.
//
// MapContainer is a passthrough so the pages that render a map still put their
// surrounding content — the stop list, the status buttons, the notes — under
// test. The map itself is not exercised anywhere.
vi.mock('react-leaflet', () => {
  // useMap hands a component the live Leaflet map. LocationPicker's FollowPin
  // calls setView on it to move the view when the pin changes, so the stub has
  // to be an object rather than null. If another component starts calling a
  // method that is not here, it fails the same way this one did — add it then
  // rather than guessing at the full Leaflet API now.
  const map = { setView: () => map };

  const passthrough = ({ children }: { children?: unknown }) =>
    createElement('div', { 'data-testid': 'map' }, children as never);
  const empty = () => null;

  return {
    MapContainer: passthrough,
    TileLayer: empty,
    CircleMarker: empty,
    Polyline: empty,
    Marker: empty,
    Popup: empty,
    // ClickToPin attaches its click handler through this hook. It returns the
    // map in real Leaflet; the component ignores it.
    useMapEvents: () => map,
    useMap: () => map,
  };
});

afterEach(() => {
  cleanup();
  // The cart persists to localStorage. Without this, one test's cart becomes
  // the next test's starting state.
  localStorage.clear();
});
