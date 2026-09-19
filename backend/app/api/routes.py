from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from app.core.security import current_user, hash_password, make_token, require_roles, verify_password
from app.db.session import get_db
from app.models.entities import Category, Listing, Order, User
from app.schemas.api import AuthOut, ListingCreate, LoginInput, OrderCreate, RegisterInput, UserOut
from app.services.freshness import freshness

router=APIRouter()
def user_out(u:User): return UserOut(id=u.id,name=u.name,email=u.email,role=u.role)
def listing_out(x:Listing):
    status, hours=freshness(x)
    return {'id':x.id,'title':x.title,'category':x.category.name,'farmer_name':x.farmer.name,'farmer_id':x.farmer_id,'location':x.location_text,'price_per_unit':x.price_per_unit,'unit':x.unit,'available_quantity':x.available_quantity,'organic':x.organic,'freshness_status':status,'remaining_hours':hours,'image_url':x.image_url,'verified':x.farmer.role=='farmer','reason':'Fresh today and close to you'}
@router.post('/auth/register',response_model=AuthOut)
def register(data:RegisterInput,db:Session=Depends(get_db)):
    if data.role not in {'buyer','farmer'}: raise HTTPException(422,'Choose buyer or farmer')
    if db.scalar(select(User).where(User.email==data.email)): raise HTTPException(409,'An account already exists for that email')
    user=User(name=data.name,email=data.email,password_hash=hash_password(data.password),role=data.role,phone=data.phone);db.add(user);db.commit();db.refresh(user);return AuthOut(access_token=make_token(user),user=user_out(user))
@router.post('/auth/login',response_model=AuthOut)
def login(data:LoginInput,db:Session=Depends(get_db)):
    user=db.scalar(select(User).where(User.email==data.email))
    if not user or not verify_password(data.password,user.password_hash): raise HTTPException(401,'Incorrect email or password')
    return AuthOut(access_token=make_token(user),user=user_out(user))
@router.get('/auth/me',response_model=UserOut)
def me(user:User=Depends(current_user)): return user_out(user)
@router.get('/categories')
def categories(db:Session=Depends(get_db)): return [{'id':x.id,'name':x.name,'default_lifespan_hours':x.default_lifespan_hours} for x in db.scalars(select(Category)).all()]
@router.get('/listings')
def listings(db:Session=Depends(get_db)):
    rows=db.scalars(select(Listing).options(joinedload(Listing.farmer),joinedload(Listing.category)).where(Listing.status=='active')).unique().all()
    return [listing_out(x) for x in rows if freshness(x)[0]!='Expired']
@router.get('/listings/{listing_id}')
def listing(listing_id:int,db:Session=Depends(get_db)):
    x=db.scalar(select(Listing).options(joinedload(Listing.farmer),joinedload(Listing.category)).where(Listing.id==listing_id))
    if not x: raise HTTPException(404,'Listing not found')
    return listing_out(x)
@router.post('/listings')
def create_listing(data:ListingCreate,user:User=Depends(require_roles('farmer')),db:Session=Depends(get_db)):
    if data.harvest_time and data.harvest_time>datetime.utcnow(): raise HTTPException(422,'Harvest time cannot be in the future')
    if not db.get(Category,data.category_id): raise HTTPException(404,'Category not found')
    x=Listing(farmer_id=user.id,**data.model_dump());db.add(x);db.commit();db.refresh(x);return {'id':x.id}
@router.post('/orders')
def create_order(data:OrderCreate,user:User=Depends(require_roles('buyer')),db:Session=Depends(get_db)):
    x=db.get(Listing,data.listing_id)
    if not x or x.status!='active': raise HTTPException(404,'Listing is unavailable')
    if x.farmer_id==user.id: raise HTTPException(422,'You cannot order your own listing')
    if freshness(x)[0]=='Expired': raise HTTPException(422,'This listing has expired')
    if data.quantity>x.available_quantity: raise HTTPException(422,'Requested quantity is unavailable')
    order=Order(buyer_id=user.id,farmer_id=x.farmer_id,listing_id=x.id,quantity=data.quantity,total_amount=data.quantity*x.price_per_unit,payment_mode=data.payment_mode);db.add(order);db.commit();return {'id':order.id,'status':order.status}
@router.get('/recommendations/listings')
def recommendations(user:User=Depends(current_user),db:Session=Depends(get_db)):
    return listings(db)[:4]
@router.get('/admin/metrics')
def metrics(user:User=Depends(require_roles('admin')),db:Session=Depends(get_db)):
    return {'users':len(db.scalars(select(User)).all()),'listings':len(db.scalars(select(Listing)).all()),'orders':len(db.scalars(select(Order)).all()),'subscriptions':3}
