import type { Address, AdminListing, AdminMetrics, AdminUser, Category, CheckoutResult, CreateSubscriptionPayload, DashboardSummary, DeliveryMethod, DeliveryRoute, DeliveryStatus, Farmer, Forecast, Listing, ListingModerationStatus, ListingQuery, Order, OrderStatus, PaginatedListings, PaymentMethod, Report, ReportAgainstMe, ReportReason, ReportStatus, Subscription, User } from '../types';
const base = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const headers = () => ({ 'Content-Type': 'application/json', ...(localStorage.token ? { Authorization: `Bearer ${localStorage.token}` } : {}) });
async function request<T>(path: string, options?: RequestInit): Promise<T> { const r = await fetch(base + path, { ...options, headers: { ...headers(), ...options?.headers } }); if (!r.ok) throw new Error((await r.json().catch(() => ({ detail: 'Request failed' }))).detail); return r.json(); }

async function upload<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append('file', file);
  const r = await fetch(base + path, {
    method: 'POST',
    headers: localStorage.token ? { Authorization: `Bearer ${localStorage.token}` } : {},
    body: form,
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({ detail: 'Upload failed' }))).detail);
  return r.json();
}

function toQueryString(params: Record<string, unknown>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue;
    search.append(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : '';
}

export type RegisterPayload = {
  name: string;
  email: string;
  password: string;
  role: 'buyer' | 'farmer';
  phone?: string;
};

export type ProfileUpdatePayload = {
  name?: string;
  email?: string;
  phone?: string;
};

export type ListingUpdatePayload = {
  category_id?: number;
  title?: string;
  description?: string;
  price_per_unit?: number;
  unit?: string;
  available_quantity?: number;
  harvest_time?: string;
  lifespan_hours?: number;
  organic?: boolean;
  bulk_available?: boolean;
  location_text?: string;
  latitude?: number;
  longitude?: number;
  image_url?: string;
};

export type CreateListingPayload = Omit<ListingUpdatePayload, 'lifespan_hours'> & {
  category_id: number;
  title: string;
  price_per_unit: number;
  available_quantity: number;
  lifespan_hours: number;
  location_text: string;
};

export type AddressPayload = {
  label: string;
  line1: string;
  line2?: string;
  city: string;
  state: string;
  pincode: string;
  phone?: string;
  latitude?: number;
  longitude?: number;
  is_default?: boolean;
};

export type AddressUpdatePayload = {
  label?: string;
  line1?: string;
  line2?: string;
  city?: string;
  state?: string;
  pincode?: string;
  phone?: string;
  latitude?: number | null;
  longitude?: number | null;
  is_default?: boolean;
};

export type PaymentMethodPayload = {
  label: string;
  method_type: 'upi' | 'card' | 'cod';
  last4?: string;
  is_default?: boolean;
};

export type CheckoutPayload = {
  items: { listing_id: number; quantity: number }[];
  delivery_method: DeliveryMethod;
  delivery_address?: string;
  delivery_latitude?: number;
  delivery_longitude?: number;
  payment_mode?: string;
  payment_label?: string;
};

export type ReopenResult = {
  id: number;
  status: string;
  quantity: number;
  total_amount: number;
  capped: boolean;
};

export type ModerationResult = {
  id: number;
  status: ListingModerationStatus;
  moderation_note?: string | null;
  cancelled_orders: number;
};

export type ListingSaveResult = {
  id: number;
  lifespan_hours: number;
  lifespan_locked?: boolean;
  expires_at: string;
};

export const api = {
  listings: (params: ListingQuery = {}) => request<PaginatedListings>(`/listings${toQueryString(params)}`),
  listing: (id: number) => request<Listing>(`/listings/${id}`),
  farmerListings: () => request<Listing[]>('/farmer/listings'),
  recommendations: () => request<Listing[]>('/recommendations/listings'),
  categories: () => request<Category[]>('/categories'),
  farmers: () => request<Farmer[]>('/farmers'),
  login: (email: string, password: string) => request<{access_token:string; user:User}>('/auth/login', { method:'POST', body:JSON.stringify({email,password}) }),
  register: (data: RegisterPayload) => request<{access_token:string; user:User}>('/auth/register', {method:'POST',body:JSON.stringify(data)}),
  me: () => request<User>('/auth/me'),
  updateProfile: (data: ProfileUpdatePayload) => request<User>('/auth/me', {method:'PATCH', body:JSON.stringify(data)}),
  changePassword: (current_password: string, new_password: string) =>
    request<{ok:boolean}>('/auth/change-password', {method:'POST', body:JSON.stringify({current_password, new_password})}),
  order: (listing_id:number, quantity:number) => request('/orders',{method:'POST',body:JSON.stringify({listing_id,quantity,payment_mode:'demo'})}),
  summary: () => request<DashboardSummary>('/dashboard/summary'),

  createListing: (data: CreateListingPayload) => request<ListingSaveResult>('/listings', {method:'POST', body:JSON.stringify(data)}),
  updateListing: (id: number, data: ListingUpdatePayload) => request<ListingSaveResult>(`/listings/${id}`, {method:'PATCH', body:JSON.stringify(data)}),
  deleteListing: (id: number, cancelOpenOrders = false) =>
    request<{id:number; status:string; cancelled_orders:number}>(
      `/listings/${id}${cancelOpenOrders ? '?cancel_open_orders=true' : ''}`,
      {method:'DELETE'},
    ),
  uploadImage: (file: File) => upload<{url:string; bytes:number}>('/uploads', file),

  orders: () => request<Order[]>('/orders'),
  cancelOrder: (id: number) => request<{id:number;status:string}>(`/orders/${id}/status`, {method:'PATCH', body:JSON.stringify({status:'cancelled'})}),
  updateOrderStatus: (id: number, status: OrderStatus) => request<{id:number;status:string}>(`/orders/${id}/status`, {method:'PATCH', body:JSON.stringify({status})}),
  reopenOrder: (id: number) => request<ReopenResult>(`/orders/${id}/reopen`, {method:'POST'}),
  checkout: (data: CheckoutPayload) => request<CheckoutResult>('/orders/checkout', {method:'POST', body:JSON.stringify(data)}),

  deliveryRoute: () => request<DeliveryRoute>('/farmer/deliveries'),
  updateDeliveryStatus: (orderId: number, status: DeliveryStatus, note?: string) =>
    request<{id:number; delivery_status:DeliveryStatus; delivery_note?:string|null}>(
      `/orders/${orderId}/delivery-status`,
      {method:'PATCH', body:JSON.stringify({status, note})},
    ),

  forecast: () => request<Forecast>('/forecast'),

  addresses: () => request<Address[]>('/addresses'),
  createAddress: (data: AddressPayload) => request<Address>('/addresses', {method:'POST', body:JSON.stringify(data)}),
  updateAddress: (id: number, data: AddressUpdatePayload) => request<Address>(`/addresses/${id}`, {method:'PATCH', body:JSON.stringify(data)}),
  deleteAddress: (id: number) => request<{ok:boolean}>(`/addresses/${id}`, {method:'DELETE'}),

  paymentMethods: () => request<PaymentMethod[]>('/payment-methods'),
  createPaymentMethod: (data: PaymentMethodPayload) => request<PaymentMethod>('/payment-methods', {method:'POST', body:JSON.stringify(data)}),
  deletePaymentMethod: (id: number) => request<{ok:boolean}>(`/payment-methods/${id}`, {method:'DELETE'}),

  fileReport: (data: { listing_id: number; reason: ReportReason; details?: string }) => request<{id:number;status:string}>('/reports', {method:'POST', body:JSON.stringify(data)}),
  reportsAgainstMe: () => request<ReportAgainstMe>('/reports/against-me'),
  allReports: () => request<Report[]>('/reports'),
  resolveReport: (id: number, status: Exclude<ReportStatus, 'open'>, note?: string) =>
    request<{id:number; status:ReportStatus; resolution_note?:string|null}>(
      `/admin/reports/${id}`,
      {method:'PATCH', body:JSON.stringify({status, note})},
    ),

  subscriptions: () => request<Subscription[]>('/subscriptions'),
  createSubscription: (data: CreateSubscriptionPayload) => request<{id:number; next_cycle_at:string}>('/subscriptions', {method:'POST', body:JSON.stringify(data)}),
  generateDueSubscriptions: () => request<{generated:number; skipped:number; raced:boolean}>('/subscriptions/generate-due', {method:'POST'}),

  adminMetrics: () => request<AdminMetrics>('/admin/metrics'),
  adminUsers: () => request<AdminUser[]>('/admin/users'),
  adminSetUserActive: (id: number, is_active: boolean) =>
    request<{id:number; is_active:boolean; listings_affected:number}>(`/admin/users/${id}/active`, {method:'PATCH', body:JSON.stringify({is_active})}),
  adminListings: () => request<AdminListing[]>('/admin/listings'),
  adminOrders: () => request<Order[]>('/admin/orders'),
  adminSetListingStatus: (
    id: number,
    status: ListingModerationStatus,
    moderation_note?: string,
    cancel_open_orders?: boolean,
  ) => request<ModerationResult>(`/admin/listings/${id}/status`, {
    method:'PATCH',
    body: JSON.stringify({ status, moderation_note, cancel_open_orders: cancel_open_orders ?? false }),
  }),
  adminCreateCategory: (name: string, default_lifespan_hours: number) =>
    request<Category>('/admin/categories', {method:'POST', body:JSON.stringify({name, default_lifespan_hours})}),
  adminUpdateCategory: (id: number, name?: string, default_lifespan_hours?: number) =>
    request<Category>(`/admin/categories/${id}`, {method:'PATCH', body:JSON.stringify({name, default_lifespan_hours})}),
  adminDeleteCategory: (id: number) => request<{ok:boolean}>(`/admin/categories/${id}`, {method:'DELETE'}),
  adminSubscriptions: () => request<Subscription[]>('/admin/subscriptions'),
  adminCancelSubscription: (id: number) =>
    request<{id:number; status:string; cancelled_at:string}>(`/admin/subscriptions/${id}`, {method:'DELETE'}),
};
