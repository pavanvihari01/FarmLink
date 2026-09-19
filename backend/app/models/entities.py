from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
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
    organic: Mapped[bool] = mapped_column(Boolean, default=False)
    bulk_available: Mapped[bool] = mapped_column(Boolean, default=False)
    location_text: Mapped[str] = mapped_column(String(140))
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default='active')
    farmer: Mapped[User] = relationship(back_populates='listings')
    category: Mapped[Category] = relationship()

class Order(Base):
    __tablename__ = 'orders'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    farmer_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    listing_id: Mapped[int] = mapped_column(ForeignKey('listings.id'))
    quantity: Mapped[float] = mapped_column(Float)
    total_amount: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default='requested')
    payment_mode: Mapped[str] = mapped_column(String(30), default='demo')
    payment_status: Mapped[str] = mapped_column(String(20), default='simulated')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
