from datetime import datetime, timedelta
from sqlalchemy import select
from app.core.security import hash_password
from app.models.entities import Category, Listing, User

def seed(db):
    if db.scalar(select(User).limit(1)): return
    users=[User(name='Anita Verma',email='farmer@farmlink.demo',password_hash=hash_password('Demo123!'),role='farmer'),User(name='Kaveri FPO',email='fpo@farmlink.demo',password_hash=hash_password('Demo123!'),role='farmer'),User(name='Meera Shah',email='buyer@farmlink.demo',password_hash=hash_password('Demo123!'),role='buyer'),User(name='Raj Bulk Foods',email='bulk@farmlink.demo',password_hash=hash_password('Demo123!'),role='buyer'),User(name='FarmLink Admin',email='admin@farmlink.demo',password_hash=hash_password('Demo123!'),role='admin')]
    db.add_all(users);db.flush()
    categories=[Category(name='Tomato',default_lifespan_hours=96),Category(name='Spinach',default_lifespan_hours=24),Category(name='Cucumber',default_lifespan_hours=72),Category(name='Okra',default_lifespan_hours=48),Category(name='Carrot',default_lifespan_hours=168)]
    db.add_all(categories);db.flush()
    now=datetime.utcnow(); img='/images/market-harvest.png'
    rows=[('Vine-ripe Tomatoes',0,0,46,96,now-timedelta(hours=15),'Nashik, Maharashtra'),('Morning Spinach',0,1,38,24,now-timedelta(hours=9),'Pune, Maharashtra'),('Field Cucumbers',1,2,52,72,now-timedelta(hours=12),'Satara, Maharashtra'),('Tender Okra',1,3,64,48,now-timedelta(hours=29),'Kolhapur, Maharashtra'),('Sweet Carrots',0,4,56,168,now-timedelta(hours=12),'Nashik, Maharashtra'),('Market Tomatoes',1,0,42,96,now-timedelta(hours=48),'Pune, Maharashtra')]
    for title,farmer,cat,price,life,harvest,location in rows:
        db.add(Listing(
            farmer_id=users[farmer].id,
            category_id=categories[cat].id,
            title=title,
            description='Harvested locally for direct delivery.',
            image_url=img,
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
