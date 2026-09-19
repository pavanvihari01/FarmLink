export type Freshness = 'Fresh' | 'Use Soon' | 'Expiring' | 'Expired';
export type Listing = { id: number; title: string; category: string; farmer_name: string; farmer_id: number; location: string; price_per_unit: number; unit: string; available_quantity: number; organic: boolean; freshness_status: Freshness; remaining_hours: number; image_url: string; verified: boolean; reason?: string; };
export type User = { id: number; name: string; email: string; role: 'farmer' | 'buyer' | 'admin'; };
