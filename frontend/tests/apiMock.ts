/**
 * A complete stand-in for src/lib/api.ts.
 *
 * Every method the app calls must exist here. A partial mock produces
 * "api.something is not a function" deep inside a page component, which reads
 * like an app bug and is not one — it is this file being out of date.
 *
 * Test files wire it up with an async factory so there is no hoisting problem:
 *
 *   vi.mock('../src/lib/api', async () => ({ api: (await import('./apiMock')).api }));
 */
import { vi } from 'vitest';

const ok = <T>(value: T) => vi.fn().mockResolvedValue(value);
const fail = (message: string) => vi.fn().mockRejectedValue(new Error(message));

/** Fresh defaults. Called at import, and again by resetApiMock between tests. */
function defaults() {
  return {
    // Listings
    listings: ok({ items: [], total: 0, page: 1, pages: 1, page_size: 12 }),
    listing: ok(null),
    farmerListings: ok([]),
    recommendations: ok([]),
    categories: ok([]),
    farmers: ok([]),

    // Auth
    login: fail('not signed in'),
    register: fail('not signed in'),
    // App calls this only when a token is present; no token means no call.
    me: fail('no session'),
    updateProfile: fail('no session'),
    changePassword: fail('no session'),

    // Orders
    order: fail('not signed in'),
    summary: ok({ open_orders: 0 }),
    orders: ok([]),
    cancelOrder: fail('not signed in'),
    updateOrderStatus: fail('not signed in'),
    reopenOrder: fail('not signed in'),
    checkout: ok({ created: [], failed: [], delivery_method: 'delivery' }),

    // Listings — writes
    createListing: fail('not signed in'),
    updateListing: fail('not signed in'),
    deleteListing: fail('not signed in'),
    uploadImage: fail('not signed in'),

    // Delivery
    deliveryRoute: ok({ origin: null, stops: [], unroutable: [], total_distance_km: null, note: null }),
    updateDeliveryStatus: fail('not signed in'),

    forecast: ok(null),

    // Addresses
    addresses: ok([]),
    createAddress: fail('not signed in'),
    updateAddress: fail('not signed in'),
    deleteAddress: fail('not signed in'),

    // Payment methods
    paymentMethods: ok([]),
    createPaymentMethod: fail('not signed in'),
    deletePaymentMethod: fail('not signed in'),

    // Reports
    fileReport: fail('not signed in'),
    reportsAgainstMe: ok({ count: 0, threshold: 3, locked: false }),
    allReports: ok([]),
    resolveReport: fail('not signed in'),

    // Subscriptions
    subscriptions: ok([]),
    createSubscription: fail('not signed in'),
    generateDueSubscriptions: ok({ generated: 0, skipped: 0, raced: false }),

    // Admin
    adminMetrics: ok({
      users: 0,
      listings: 0,
      orders: 0,
      reports_open: 0,
      categories: 0,
      subscriptions: 0,
      deliveries_open: 0,
    }),
    adminUsers: ok([]),
    adminSetUserActive: fail('not signed in'),
    adminListings: ok([]),
    adminOrders: ok([]),
    adminSetListingStatus: fail('not signed in'),
    adminCreateCategory: fail('not signed in'),
    adminUpdateCategory: fail('not signed in'),
    adminDeleteCategory: fail('not signed in'),
    adminSubscriptions: ok([]),
    adminCancelSubscription: fail('not signed in'),
  };
}

export const api = defaults();

/**
 * Put every method back to its default and clear call history.
 *
 * Call from beforeEach. Without it, one test's mockResolvedValue is the next
 * test's starting state — the mock equivalent of the identity-map staleness
 * that bit the backend suite twice.
 */
export function resetApiMock(): void {
  Object.assign(api, defaults());
}
