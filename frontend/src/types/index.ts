export type Freshness = 'Fresh' | 'Use Soon' | 'Expiring' | 'Expired';

export type ListingModerationStatus = 'active' | 'suspended' | 'removed';

export type VerificationStatus = 'unverified' | 'verified';

export type Listing = {
  id: number;
  title: string;
  description: string;
  category: string;
  category_id: number;
  farmer_name: string;
  farmer_id: number;
  location: string;
  price_per_unit: number;
  unit: string;
  available_quantity: number;
  organic: boolean;
  bulk_available: boolean;
  freshness_status: Freshness;
  remaining_hours: number;
  image_url: string;
  // True only when the owning farmer's verification_status is 'verified'.
  // Set by an admin through PATCH /admin/users/{id}/verification.
  verified: boolean;
  latitude: number | null;
  longitude: number | null;
  distance_km: number | null;
  // Present on the farmer's own listing view; always 'active' in the public
  // marketplace, which filters everything else out.
  status?: ListingModerationStatus;
  moderation_note?: string | null;
  // Only the recommendations endpoint sets this, and only when it has a real
  // signal to name. Absent everywhere else rather than carrying a stock line.
  reason?: string;
};

export type User = {
  id: number;
  name: string;
  email: string;
  role: 'farmer' | 'buyer' | 'admin';
  is_active?: boolean;
  phone?: string | null;
  // Optional so object literals in test fixtures that predate the field still
  // compile. Absent reads as unverified, which is the correct default.
  verification_status?: VerificationStatus;
};

export type Farmer = {
  id: number;
  name: string;
  location?: string | null;
};

export type Category = {
  id: number;
  name: string;
  default_lifespan_hours: number;
};

export type ListingQuery = {
  q?: string;
  location?: string;
  farmer?: string;
  category_id?: number;
  min_price?: number;
  max_price?: number;
  organic?: boolean;
  bulk_available?: boolean;
  freshness_status?: string;
  sort?: ListingSort;
  page?: number;
  page_size?: number;
  lat?: number;
  lng?: number;
};

export type ListingSort = 'freshness' | 'price_asc' | 'price_desc' | 'newest' | 'nearest';

export type PaginatedListings = {
  items: Listing[];
  total: number;
  page: number;
  pages: number;
  page_size: number;
};

export type DashboardSummary = {
  open_orders: number;
  active_listings?: number;
  expired_listings?: number;
  available_now?: number;
  categories?: number;
  open_deliveries?: number;
};

export type Address = {
  id: number;
  label: string;
  line1: string;
  line2?: string | null;
  city: string;
  state: string;
  pincode: string;
  phone?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  is_default: boolean;
};

export type PaymentMethod = {
  id: number;
  label: string;
  method_type: 'upi' | 'card' | 'cod';
  last4?: string | null;
  is_default: boolean;
};

export type OrderStatus = 'requested' | 'accepted' | 'completed' | 'rejected' | 'cancelled';

export type DeliveryMethod = 'pickup' | 'delivery';
export type DeliveryStatus = 'pending' | 'out_for_delivery' | 'delivered' | 'failed';

export type Order = {
  id: number;
  listing_id: number;
  listing_title: string;
  counterparty: string;
  quantity: number;
  total_amount: number;
  status: OrderStatus;
  created_at: string;
  delivery_address?: string | null;
  payment_label?: string | null;
  subscription_id?: number | null;
  delivery_method: DeliveryMethod;
  delivery_latitude?: number | null;
  delivery_longitude?: number | null;
  delivery_status?: DeliveryStatus | null;
  delivery_note?: string | null;
  // Only present on the admin order list.
  farmer_name?: string;
};

export type CheckoutResult = {
  created: { listing_id: number; order_id: number; title: string; quantity: number; total_amount: number }[];
  failed: { listing_id: number; reason: string }[];
  delivery_address?: string | null;
  payment_label?: string | null;
  delivery_method: DeliveryMethod;
};

export type ReportReason = 'fake_lifespan' | 'wrong_quantity' | 'bad_quality' | 'no_show' | 'other';
export type ReportStatus = 'open' | 'resolved' | 'dismissed';

export type ReportAgainstMe = {
  count: number;
  threshold: number;
  locked: boolean;
};

export type Report = {
  id: number;
  reporter: string;
  reported_user: string;
  listing_id: number;
  listing_title: string;
  reason: ReportReason;
  details?: string | null;
  status: ReportStatus;
  resolution_note?: string | null;
  created_at: string;
};

export type SubscriptionCycle = {
  id: number;
  scheduled_for: string;
  status: 'generated' | 'skipped';
  order_id?: number | null;
  reason?: string | null;
};

export type Subscription = {
  id: number;
  buyer_id: number;
  buyer_name: string;
  farmer_id: number;
  farmer_name: string;
  category: string;
  category_id: number;
  quantity: number;
  unit: string;
  frequency_days: number;
  status: 'active' | 'cancelled';
  next_cycle_at: string;
  delivery_address: string;
  // Present since subscriptions became deliveries. Absent on rows created
  // before that rule, which is what the page checks when deciding whether a
  // subscription can still be fulfilled.
  delivery_latitude?: number | null;
  delivery_longitude?: number | null;
  payment_label?: string | null;
  created_at: string;
  cancelled_at?: string | null;
  recent_cycles: SubscriptionCycle[];
};

export type CreateSubscriptionPayload = {
  farmer_id: number;
  category_id: number;
  quantity: number;
  unit: string;
  frequency_days: 7 | 14 | 30;
  delivery_address: string;
  // Every subscription is a delivery, so the destination must be pinned. The
  // backend rejects a subscription without one.
  delivery_latitude: number;
  delivery_longitude: number;
  payment_label?: string;
};

export type DeliveryStop = {
  order_id: number;
  listing_title: string;
  buyer_name: string;
  address: string;
  quantity: number;
  delivery_status: DeliveryStatus | null;
  delivery_note?: string | null;
  created_at: string;
  latitude?: number;
  longitude?: number;
  leg_distance_km?: number;
  distance_from_origin_km?: number;
};

export type DeliveryRoute = {
  origin: { latitude: number; longitude: number } | null;
  stops: DeliveryStop[];
  unroutable: DeliveryStop[];
  total_distance_km: number | null;
  note: string | null;
};

export type ForecastTrend = 'rising' | 'falling' | 'steady';

export type ForecastItem = {
  category_id: number;
  category: string;
  location: string;
  unit: string;
  order_count: number;
  past_quantity: number;
  weekly_rate: number;
  forecast_quantity: number;
  recent_quantity: number;
  prior_quantity: number;
  trend: ForecastTrend;
  trend_pct: number | null;
  has_enough_data: boolean;
};

export type Forecast = {
  window_weeks: number;
  forecast_weeks: number;
  window_start: string;
  generated_at: string;
  order_count: number;
  items: ForecastItem[];
  note: string | null;
};

export type AdminMetrics = {
  users: number;
  listings: number;
  orders: number;
  reports_open: number;
  categories: number;
  subscriptions: number;
  deliveries_open: number;
};

export type AdminUser = {
  id: number;
  name: string;
  email: string;
  role: 'farmer' | 'buyer' | 'admin';
  is_active: boolean;
  created_at: string;
  listing_count: number;
  report_count: number;
  verification_status?: VerificationStatus;
};

export type AdminListing = {
  id: number;
  title: string;
  category: string;
  farmer_name: string;
  price_per_unit: number;
  unit: string;
  available_quantity: number;
  location: string;
  status: ListingModerationStatus;
  moderation_note?: string | null;
  image_url: string;
  open_orders: number;
  listing_time: string;
};
