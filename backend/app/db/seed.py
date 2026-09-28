from datetime import datetime, timedelta
from sqlalchemy import select
from app.core.security import hash_password
from app.models.entities import Category, Listing, User

# Demo photos bundled under frontend/public/products/. Keyed by category name.
# Every vegetable that has a photo is listed, so a category added through the
# admin panel picks up the right image instead of falling back.
CATEGORY_IMAGES = {
    'Ash Gourd': '/products/ASH_GOURD.jpeg',
    'Beetroot': '/products/BEETROOT.jpeg',
    'Bitter Gourd': '/products/BITTER_GOURD.jpeg',
    'Bottle Gourd': '/products/BOTTLE_GOURD.jpeg',
    'Cabbage': '/products/CABBAGE.jpeg',
    'Capsicum': '/products/CAPSICUM.jpeg',
    'Carrot': '/products/CARROT.jpeg',
    'Cauliflower': '/products/CAULIFLOWER.jpeg',
    'Cluster Beans': '/products/CLUSTER_BEANS.jpeg',
    'Coriander': '/products/CORIANDER.jpeg',
    'Corn': '/products/CORN.jpeg',
    'Cucumber': '/products/CUCUMBER.jpeg',
    'Curry Leaves': '/products/CURRY_LEAVES.jpeg',
    'Drumstick': '/products/DRUMSTICK.jpeg',
    'Eggplant': '/products/EGGPLANT.jpeg',
    'French Beans': '/products/FRENCH_BEANS.jpeg',
    'Green Chilli': '/products/GREEN_CHILLI.jpeg',
    'Green Peas': '/products/GREEN_PEAS.jpeg',
    'Ivy Gourd': '/products/IVY_GOURD.jpeg',
    'Okra': '/products/LADYS_FINGER.jpeg',
    'Lemon': '/products/LEMON.jpeg',
    'Mint': '/products/MINT.jpeg',
    'Onion': '/products/ONION.jpeg',
    'Potato': '/products/POTATO.jpeg',
    'Pumpkin': '/products/PUMPKIN.jpeg',
    'Radish': '/products/RADISH.jpeg',
    'Raw Banana': '/products/RAW_BANANA.jpeg',
    'Ridge Gourd': '/products/RIDGE_GOURD.jpeg',
    'Snake Gourd': '/products/SNAKE_GOURD.jpeg',
    'Spinach': '/products/SPINACH.jpeg',
    'Sweet Potato': '/products/SWEET_POTATO.jpeg',
    'Tomato': '/products/TOMATO.jpeg',
}

# Fallback for a category with no bundled photo. Matches the column default.
DEFAULT_IMAGE = '/images/market-harvest.png'

def seed(db):
    if db.scalar(select(User).limit(1)): return
    # Both demo farmers are seeded verified so the badge renders in a fresh
    # install. Every account defaults to 'unverified'.
    users=[
        User(name='Anita Verma',email='farmer@farmlink.demo',password_hash=hash_password('Demo123!'),role='farmer',verification_status='verified'),
        User(name='Kaveri FPO',email='fpo@farmlink.demo',password_hash=hash_password('Demo123!'),role='farmer',verification_status='verified'),
        User(name='Meera Shah',email='buyer@farmlink.demo',password_hash=hash_password('Demo123!'),role='buyer'),
        User(name='Raj Bulk Foods',email='bulk@farmlink.demo',password_hash=hash_password('Demo123!'),role='buyer'),
        User(name='FarmLink Admin',email='admin@farmlink.demo',password_hash=hash_password('Demo123!'),role='admin'),
    ]
    db.add_all(users);db.flush()
    categories=[Category(name='Tomato',default_lifespan_hours=96),Category(name='Spinach',default_lifespan_hours=24),Category(name='Cucumber',default_lifespan_hours=72),Category(name='Okra',default_lifespan_hours=48),Category(name='Carrot',default_lifespan_hours=168)]
    db.add_all(categories);db.flush()
    now=datetime.utcnow()
    rows=[('Vine-ripe Tomatoes',0,0,46,96,now-timedelta(hours=15),'Nashik, Maharashtra'),('Morning Spinach',0,1,38,24,now-timedelta(hours=9),'Pune, Maharashtra'),('Field Cucumbers',1,2,52,72,now-timedelta(hours=12),'Satara, Maharashtra'),('Tender Okra',1,3,64,48,now-timedelta(hours=29),'Kolhapur, Maharashtra'),('Sweet Carrots',0,4,56,168,now-timedelta(hours=12),'Nashik, Maharashtra'),('Market Tomatoes',1,0,42,96,now-timedelta(hours=48),'Pune, Maharashtra')]
    for title,farmer,cat,price,life,harvest,location in rows:
        category=categories[cat]
        db.add(Listing(
            farmer_id=users[farmer].id,
            category_id=category.id,
            title=title,
            description='Harvested locally for direct delivery.',
            image_url=CATEGORY_IMAGES.get(category.name,DEFAULT_IMAGE),
            price_per_unit=price,
            unit='kg',
            available_quantity=35,
            harvest_time=harvest,
            # Set explicitly rather than defaulting to now(), so expires_at is
            # consistent with harvest_time + lifespan_hours.
            listing_time=harvest,
            lifespan_hours=life,
            expires_at=harvest+timedelta(hours=life),
            organic=cat in {1,2},
            bulk_available=True,
            location_text=location,
        ))
    db.commit()