from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default='buyer')
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # 'unverified' | 'verified'. Set by an admin, never by the account holder.
    # Read by listing_out to decide whether a listing shows the badge. Only
    # farmers can hold 'verified': the badge is a claim about a seller, and
    # buyers have no listings for it to appear on.
    verification_status: Mapped[str] = mapped_column(
        String(20), default='unverified', server_default='unverified'
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    listings: Mapped[list['Listing']] = relationship(back_populates='farmer')

class Category(Base):
    __tablename__ = 'categories'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    default_lifespan_hours: Mapped[int] = mapped_column(Integer)

class Listing(Base):
    __tablename__ = 'listings'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    category_id: Mapped[int] = mapped_column(ForeignKey('categories.id'))
    title: Mapped[str] = mapped_column(String(140))
    description: Mapped[str] = mapped_column(Text, default='')
    image_url: Mapped[str] = mapped_column(String(500), default='/images/market-harvest.png')
    price_per_unit: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(20), default='kg')
    available_quantity: Mapped[float] = mapped_column(Float)
    harvest_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    listing_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    lifespan_hours: Mapped[int] = mapped_column(Integer)
    # Precomputed as (harvest_time or listing_time) + lifespan_hours. Kept as a
    # stored column so sorting and expiry filtering do not have to recompute the
    # base time on every query. Maintained in create_listing and update_listing;
    # backfilled by migration 0006 for rows that predate it.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    organic: Mapped[bool] = mapped_column(Boolean, default=False)
    bulk_available: Mapped[bool] = mapped_column(Boolean, default=False)
    location_text: Mapped[str] = mapped_column(String(140))
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 'active' | 'suspended' | 'removed'. Suspended is reversible; removed is
    # retained in the database so order history still resolves, but the listing
    # is no longer reachable through the public endpoints.
    status: Mapped[str] = mapped_column(String(20), default='active')
    # Free-text reason recorded by an admin — or by the farmer, on self-removal.
    moderation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # True when this listing was suspended automatically because its farmer was
    # deactivated, rather than by an admin acting on the listing itself.
    # Reactivation restores exactly these, so a listing an admin suspended by
    # hand stays suspended. Any manual status change clears it.
    suspended_by_deactivation: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default='0'
    )
    farmer: Mapped[User] = relationship(back_populates='listings')
    category: Mapped[Category] = relationship()

class Address(Base):
    __tablename__ = 'addresses'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    label: Mapped[str] = mapped_column(String(60))
    line1: Mapped[str] = mapped_column(String(200))
    line2: Mapped[str | None] = mapped_column(String(200), nullable=True)
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(100))
    pincode: Mapped[str] = mapped_column(String(12))
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # Optional. Set by the address form's map picker. An address without a pin
    # still works for pickup-only ordering; it just cannot be placed on a
    # delivery route.
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class PaymentMethod(Base):
    __tablename__ = 'payment_methods'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    label: Mapped[str] = mapped_column(String(60))
    # 'upi' | 'card' | 'cod'. Nothing sensitive is stored: cards keep only a
    # label and a fake last-4. There is no gateway behind any of this.
    method_type: Mapped[str] = mapped_column(String(20))
    last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Report(Base):
    __tablename__ = 'reports'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    # Denormalized from the listing's farmer so counting reports per user is a
    # single indexed query rather than a join.
    reported_user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey('listings.id'))
    # 'fake_lifespan' | 'wrong_quantity' | 'bad_quality' | 'no_show' | 'other'
    reason: Mapped[str] = mapped_column(String(40))
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 'open' | 'resolved' | 'dismissed'. Only an admin moves it off 'open'.
    status: Mapped[str] = mapped_column(String(20), default='open')
    # Free text recorded by the admin when closing a report.
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # One report per buyer per listing. Without this, a single buyer could file
    # enough reports to trip the lock threshold on their own.
    __table_args__ = (
        UniqueConstraint('reporter_id', 'listing_id', name='uq_reports_reporter_listing'),
    )

class Subscription(Base):
    __tablename__ = 'subscriptions'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey('categories.id'))
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(20), default='kg')
    frequency_days: Mapped[int] = mapped_column(Integer)
    # 'active' | 'cancelled'. Only an admin can cancel; the buyer and farmer
    # have no control over the lifecycle once it exists.
    status: Mapped[str] = mapped_column(String(20), default='active')
    next_cycle_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    delivery_address: Mapped[str] = mapped_column(Text)
    # Optional, mirroring addresses and orders. A subscription without a pin
    # still generates a delivery order; it lands in the farmer's unroutable
    # bucket rather than on the suggested route.
    delivery_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    delivery_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    payment_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    category: Mapped[Category] = relationship()

class SubscriptionCycle(Base):
    __tablename__ = 'subscription_cycles'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subscription_id: Mapped[int] = mapped_column(ForeignKey('subscriptions.id'), index=True)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime)
    # 'generated' | 'skipped'
    status: Mapped[str] = mapped_column(String(20))
    order_id: Mapped[int | None] = mapped_column(ForeignKey('orders.id'), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint('subscription_id', 'scheduled_for', name='uq_cycles_subscription_scheduled'),
    )

class Order(Base):
    __tablename__ = 'orders'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    farmer_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    listing_id: Mapped[int] = mapped_column(ForeignKey('listings.id'))
    subscription_id: Mapped[int | None] = mapped_column(ForeignKey('subscriptions.id'), nullable=True, index=True)
    quantity: Mapped[float] = mapped_column(Float)
    total_amount: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default='requested')
    payment_mode: Mapped[str] = mapped_column(String(30), default='demo')
    payment_status: Mapped[str] = mapped_column(String(20), default='simulated')
    delivery_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    delivery_method: Mapped[str] = mapped_column(String(20), default='pickup', server_default='pickup')
    delivery_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    delivery_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 'pending' | 'out_for_delivery' | 'delivered' | 'failed'. Null for pickup
    # orders — there is no delivery to track.
    delivery_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    delivery_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status_changed_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, server_default=func.now()
    )
