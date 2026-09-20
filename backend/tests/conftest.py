"""Test harness for FarmLink.

Key design point: `TestClient(app)` is constructed WITHOUT the context
manager. Starlette only runs the startup lifespan inside `with TestClient(...)`,
so by not using `with` we skip `Base.metadata.create_all()` and `seed()`
against the real database. Tests build their own schema on an in-memory
SQLite engine instead.

StaticPool is required: without it, every connection to `sqlite://` gets a
fresh empty database, so tables created in a fixture would be invisible to
the request handler.
"""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password, make_token
from app.db.session import Base, get_db
from app.main import app
from app.models import entities  # noqa: F401  (registers models on Base.metadata)
from app.models.entities import Category, Listing, Order, User

engine = create_engine(
    'sqlite://',
    connect_args={'check_same_thread': False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = _override_get_db

@pytest.fixture(autouse=True)
def fresh_schema():
    """Every test starts with empty tables."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield

@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def make_user(db):
    def _make(email: str, role: str = 'buyer', name: str | None = None, phone: str | None = None) -> User:
        user = User(
            name=name or email.split('@')[0],
            email=email,
            password_hash=hash_password('Demo123!'),
            role=role,
            phone=phone,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return _make

@pytest.fixture
def make_category(db):
    def _make(name: str | None = None, lifespan_hours: int = 96) -> Category:
        # Category.name is unique, so an unnamed category is numbered by
        # existing row count rather than derived from the farmer.
        if name is None:
            existing = db.scalar(select(func.count()).select_from(Category)) or 0
            name = f'Test Category {existing + 1}'
        category = Category(name=name, default_lifespan_hours=lifespan_hours)
        db.add(category)
        db.commit()
        db.refresh(category)
        return category

    return _make

@pytest.fixture
def make_listing(db, make_category):
    def _make(
        farmer: User,
        quantity: float = 35.0,
        lifespan_hours: int = 96,
        age_hours: float = 0.0,
        category: Category | None = None,
        **over,
    ) -> Listing:
        """Create a listing.

        `age_hours` shifts the listing into the past, which is how the
        freshness and expiry tests produce listings at different points in
        their life. `category` lets a test pin several listings to one category
        for the category filter. Any other keyword lands on the row directly,
        so tests can set title, price, organic, coordinates, and so on.
        """
        if category is None:
            category = make_category(lifespan_hours=lifespan_hours)
        base = datetime.utcnow() - timedelta(hours=age_hours)

        # Defaults that a caller is allowed to override. `farmer_id`,
        # `category_id` and `available_quantity` are deliberately NOT in here:
        # they derive from required arguments and must not be silently
        # overridable through **over.
        fields = dict(
            title='Test Produce',
            price_per_unit=10.0,
            unit='kg',
            location_text='Test Location',
            harvest_time=base if age_hours else None,
            listing_time=base,
            lifespan_hours=lifespan_hours,
            expires_at=base + timedelta(hours=lifespan_hours),
        )
        fields.update(over)

        listing = Listing(
            farmer_id=farmer.id,
            category_id=category.id,
            available_quantity=quantity,
            **fields,
        )
        db.add(listing)
        db.commit()
        db.refresh(listing)
        return listing

    return _make

@pytest.fixture
def auth():
    def _auth(user: User) -> dict:
        return {'Authorization': f'Bearer {make_token(user)}'}

    return _auth
