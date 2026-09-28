import math
import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased, joinedload
from app.core.config import UPLOAD_DIR, get_settings
from app.core.security import current_user, hash_password, make_token, optional_user, require_roles, verify_password
from app.db.session import get_db
from app.models.entities import (
    Address, Category, Listing, Order, PaymentMethod, Report,
    Subscription, SubscriptionCycle, User,
)
from app.schemas.api import (
    AddressInput, AddressUpdateInput, AdminListingStatusInput,
    AdminVerificationInput, AuthOut,
    CategoryInput, CategoryUpdateInput, CheckoutInput, DeliveryStatusInput,
    FarmerOut, ListingCreate, ListingUpdate, LoginInput, OrderCreate,
    OrderStatusInput, PasswordChangeInput, PaymentMethodInput,
    ProfileUpdateInput, RegisterInput, ReportInput, ReportResolveInput,
    SubscriptionInput, UserActiveInput, UserOut,
)
from app.services.freshness import freshness
from app.services.images import sniff_image_type

router=APIRouter()

TERMINAL_ORDER_STATUSES={'completed','rejected','cancelled'}
OPEN_ORDER_STATUSES={'requested','accepted'}
REOPENABLE_ORDER_STATUSES={'rejected','cancelled'}
REOPEN_WINDOW_DAYS=1

ALLOWED_TRANSITIONS={
    'requested':{'accepted','rejected','cancelled'},
    'accepted':{'completed','cancelled'},
    'rejected':set(),
    'cancelled':set(),
    'completed':set(),
}

LISTING_MODERATION_STATUSES={'active','suspended','removed'}
SORT_OPTIONS={'freshness','price_asc','price_desc','newest','nearest'}
FRESHNESS_STATUSES={'Fresh','Use Soon','Expiring'}
CLOSED_DELIVERY_STATUSES={'delivered','failed'}
DELIVERY_STATUSES={'pending','out_for_delivery','delivered','failed'}

# The delivery lifecycle, separate from the order lifecycle. 'delivered' is
# terminal. 'failed' is not: a failed attempt can be retried, and retrying
# clears the failure note because a successful attempt has no failure to
# explain.
DELIVERY_TRANSITIONS={
    'pending':{'out_for_delivery','failed'},
    'out_for_delivery':{'delivered','failed'},
    'failed':{'out_for_delivery'},
    'delivered':set(),
}

DEMAND_ORDER_STATUSES={'requested','accepted','completed'}
FORECAST_WINDOW_WEEKS=8
FORECAST_HORIZON_WEEKS=2
FORECAST_MIN_ORDERS=3
TREND_THRESHOLD_PCT=15.0

ALLOWED_IMAGE_TYPES={
    'image/jpeg':'.jpg',
    'image/png':'.png',
    'image/webp':'.webp',
}
MAX_IMAGE_BYTES=10*1024*1024

DEFAULT_PAGE_SIZE=12
MAX_PAGE_SIZE=48
RECENT_CYCLES=5

RECOMMENDATION_LIMIT=4
CATEGORY_AFFINITY_PER_ORDER=2.0
CATEGORY_AFFINITY_CAP=6.0
FARMER_AFFINITY_BONUS=4.0
# Freshness contributes at most this many points. Without a cap a listing with a
# very long shelf life would outrank one the buyer has an actual history with,
# which is the opposite of the point.
FRESHNESS_SCORE_CAP_HOURS=168

def user_out(u:User): return UserOut(id=u.id,name=u.name,email=u.email,role=u.role,is_active=u.is_active,phone=u.phone,verification_status=u.verification_status)
def listing_out(x:Listing, status:str|None=None, hours:int|None=None, distance_km:float|None=None, *, reason:str|None=None, include_moderation:bool=False):
    if status is None or hours is None:
        status, hours = freshness(x)
    out={
        'id':x.id,
        'title':x.title,
        'description':x.description,
        'category':x.category.name,
        'category_id':x.category_id,
        'farmer_name':x.farmer.name,
        'farmer_id':x.farmer_id,
        'location':x.location_text,
        'price_per_unit':x.price_per_unit,
        'unit':x.unit,
        'available_quantity':x.available_quantity,
        'organic':x.organic,
        'bulk_available':x.bulk_available,
         'freshness_status':status,
        'remaining_hours':hours,
        'lifespan_hours':x.lifespan_hours,      # ← add
        'image_url':x.image_url,
        # Was a role check, which is true for every listing since only
        # farmers can create one. Now it reflects an admin decision.
        'verified':x.farmer.verification_status=='verified',
        'latitude':x.latitude,
        'longitude':x.longitude,
        'distance_km':round(distance_km, 1) if distance_km is not None else None,
        # Only meaningful to the owning farmer; the public endpoints filter to
        # active listings so buyers always see 'active' here.
        'status':x.status,
        # Internal moderation text. Null unless the caller is the owning farmer
        # or an admin, so an admin's note never reaches a public response.
        'moderation_note':x.moderation_note if include_moderation else None,
    }
    # Only the recommendations endpoint has grounds to give one. Everywhere else
    # the field is absent rather than carrying a claim nothing supports.
    if reason is not None:
        out['reason']=reason
    return out
def order_out(o:Order, listing_title:str, counterparty:str):
    return {
        'id':o.id,
        'listing_id':o.listing_id,
        'listing_title':listing_title,
        'counterparty':counterparty,
        'quantity':o.quantity,
        'total_amount':o.total_amount,
        'status':o.status,
        'created_at':o.created_at.isoformat(),
        'delivery_address':o.delivery_address,
        'payment_label':o.payment_label,
        'subscription_id':o.subscription_id,
        'delivery_method':o.delivery_method,
        'delivery_latitude':o.delivery_latitude,
        'delivery_longitude':o.delivery_longitude,
        'delivery_status':o.delivery_status,
        'delivery_note':o.delivery_note,
    }
def address_out(a:Address):
    return {'id':a.id,'label':a.label,'line1':a.line1,'line2':a.line2,'city':a.city,'state':a.state,'pincode':a.pincode,'phone':a.phone,'latitude':a.latitude,'longitude':a.longitude,'is_default':a.is_default}
def payment_out(p:PaymentMethod):
    return {'id':p.id,'label':p.label,'method_type':p.method_type,'last4':p.last4,'is_default':p.is_default}
def report_out(r:Report, reporter_name:str, reported_name:str, listing_title:str):
    return {'id':r.id,'reporter':reporter_name,'reported_user':reported_name,'listing_id':r.listing_id,'listing_title':listing_title,'reason':r.reason,'details':r.details,'status':r.status,'resolution_note':r.resolution_note,'created_at':r.created_at.isoformat()}
def cycle_out(c:SubscriptionCycle):
    return {'id':c.id,'scheduled_for':c.scheduled_for.isoformat(),'status':c.status,'order_id':c.order_id,'reason':c.reason}
def subscription_out(s:Subscription, buyer_name:str, farmer_name:str, cycles:list[SubscriptionCycle]):
    return {
        'id':s.id,
        'buyer_id':s.buyer_id,
        'buyer_name':buyer_name,
        'farmer_id':s.farmer_id,
        'farmer_name':farmer_name,
        'category':s.category.name,
        'category_id':s.category_id,
        'quantity':s.quantity,
        'unit':s.unit,
        'frequency_days':s.frequency_days,
        'status':s.status,
        'next_cycle_at':s.next_cycle_at.isoformat(),
        'delivery_address':s.delivery_address,
        'delivery_latitude':s.delivery_latitude,
        'delivery_longitude':s.delivery_longitude,
        'payment_label':s.payment_label,
        'created_at':s.created_at.isoformat(),
        'cancelled_at':s.cancelled_at.isoformat() if s.cancelled_at else None,
        'recent_cycles':[cycle_out(c) for c in cycles],
    }
def format_address(a:Address)->str:
    parts=[a.line1,a.line2,a.city,a.state,a.pincode]
    return ', '.join(p for p in parts if p)
def haversine_km(lat1:float,lng1:float,lat2:float,lng2:float)->float:
    """Great-circle distance in kilometres. Straight line, not roads."""
    radius=6371.0
    p1,p2=math.radians(lat1),math.radians(lat2)
    dp=math.radians(lat2-lat1)
    dl=math.radians(lng2-lng1)
    a=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*radius*math.asin(math.sqrt(a))
def open_order_count(db:Session,listing_id:int)->int:
    return db.scalar(select(func.count()).select_from(Order).where(Order.listing_id==listing_id,Order.status.in_(OPEN_ORDER_STATUSES))) or 0
def _delete_orphaned_upload(db:Session,url:str|None)->bool:
    """Remove an uploaded file if nothing references it any more.

    Only touches paths under /uploads/. The bundled default image is shared by
    every listing that never uploaded one, so deleting it would break the whole
    marketplace. Returns True when a file was removed.

    Called after the change is committed, so the count excludes the listing
    that just stopped using it.
    """
    if not url or not url.startswith('/uploads/'):
        return False
    still_used=db.scalar(select(func.count()).select_from(Listing).where(Listing.image_url==url)) or 0
    if still_used:
        return False
    name=url.rsplit('/',1)[-1]
    # A crafted image_url must not be able to escape the upload directory.
    if not name or '/' in name or '\\' in name or name.startswith('.'):
        return False
    target=UPLOAD_DIR/name
    try:
        if target.is_file():
            target.unlink()
            return True
    except OSError:
        # A file we cannot remove is not worth failing the request over.
        pass
    return False
def _farmer_origin(db:Session,farmer_id:int)->tuple[float,float]|None:
    """Where a farmer's delivery route starts.

    There is no farm-location field, so this uses the most recent listing that
    has coordinates. That is a stand-in, not a real farm gate.
    """
    row=db.scalar(
        select(Listing)
        .where(Listing.farmer_id==farmer_id,Listing.latitude.isnot(None),Listing.longitude.isnot(None))
        .order_by(Listing.listing_time.desc())
    )
    if row is None or row.latitude is None or row.longitude is None:
        return None
    return (row.latitude,row.longitude)
def _suggest_route(origin:tuple[float,float],stops:list[dict])->tuple[list[dict],float]:
    """Greedy nearest-neighbour ordering from the origin.

    Not optimal — this is the travelling-salesman problem and a greedy walk can
    be arbitrarily worse than the best route.
    """
    remaining=list(stops)
    ordered=[]
    total=0.0
    current=origin
    while remaining:
        nearest=min(remaining,key=lambda s:haversine_km(current[0],current[1],s['latitude'],s['longitude']))
        leg=haversine_km(current[0],current[1],nearest['latitude'],nearest['longitude'])
        total+=leg
        entry=dict(nearest)
        entry['leg_distance_km']=round(leg,1)
        ordered.append(entry)
        current=(nearest['latitude'],nearest['longitude'])
        remaining.remove(nearest)
    return ordered,total
@router.post('/auth/register',response_model=AuthOut)
def register(data:RegisterInput,db:Session=Depends(get_db)):
    if data.role not in {'buyer','farmer'}: raise HTTPException(422,'Choose buyer or farmer')
    if db.scalar(select(User).where(User.email==data.email)): raise HTTPException(409,'An account already exists for that email')
    user=User(name=data.name,email=data.email,password_hash=hash_password(data.password),role=data.role,phone=data.phone);db.add(user);db.commit();db.refresh(user);return AuthOut(access_token=make_token(user),user=user_out(user))
@router.post('/auth/login',response_model=AuthOut)
def login(data:LoginInput,db:Session=Depends(get_db)):
    user=db.scalar(select(User).where(User.email==data.email))
    if not user or not verify_password(data.password,user.password_hash): raise HTTPException(401,'Incorrect email or password')
    if not user.is_active: raise HTTPException(403,'This account has been deactivated')
    return AuthOut(access_token=make_token(user),user=user_out(user))
@router.get('/auth/me',response_model=UserOut)
def me(user:User=Depends(current_user)): return user_out(user)
@router.patch('/auth/me',response_model=UserOut)
def update_me(data:ProfileUpdateInput,user:User=Depends(current_user),db:Session=Depends(get_db)):
    if data.email is not None and data.email != user.email:
        if db.scalar(select(User).where(User.email==data.email,User.id!=user.id)):
            raise HTTPException(409,'Another account already uses that email')
        user.email=data.email
    if data.name is not None:
        user.name=data.name.strip()
    if data.phone is not None:
        user.phone=data.phone.strip() or None
    db.commit();db.refresh(user)
    return user_out(user)
@router.post('/auth/change-password')
def change_password(data:PasswordChangeInput,user:User=Depends(current_user),db:Session=Depends(get_db)):
    """Change the signed-in user's own password.

    Requires the current password. Existing tokens are NOT invalidated — the
    JWT carries only the user id and role, no password material, so a token
    issued before the change keeps working until it expires. See the README.
    """
    if not verify_password(data.current_password,user.password_hash):
        raise HTTPException(401,'That is not your current password')
    if data.current_password==data.new_password:
        raise HTTPException(422,'The new password must be different')
    user.password_hash=hash_password(data.new_password)
    db.commit()
    return {'ok':True}
@router.get('/categories')
def categories(db:Session=Depends(get_db)): return [{'id':x.id,'name':x.name,'default_lifespan_hours':x.default_lifespan_hours} for x in db.scalars(select(Category)).all()]
@router.get('/farmers',response_model=list[FarmerOut])
def farmers(db:Session=Depends(get_db)):
    rows=db.scalars(select(User).where(User.role=='farmer',User.is_active==True)).all()
    out=[]
    for u in rows:
        last=db.scalar(select(Listing).where(Listing.farmer_id==u.id).order_by(Listing.listing_time.desc()))
        out.append(FarmerOut(id=u.id,name=u.name,location=last.location_text if last else None))
    return out

# ---------------------------------------------------------------------------
# Listings — search, filter, sort, paginate
# ---------------------------------------------------------------------------
@router.get('/listings')
def listings(
    q: str | None = None,
    category_id: int | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    organic: bool | None = None,
    bulk_available: bool | None = None,
    location: str | None = None,
    farmer: str | None = None,
    freshness_status: str | None = None,
    sort: str = 'freshness',
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    lat: float | None = None,
    lng: float | None = None,
    db: Session = Depends(get_db),
):
    """One page of live listings.

    SQL narrows what it can — status, category, price, flags, text — and the
    remaining work (the freshness ratio, haversine distance) happens in Python,
    because neither is expressible portably across SQLite and PostgreSQL.
    """
    if freshness_status and freshness_status not in FRESHNESS_STATUSES:
        raise HTTPException(422, f'Freshness must be one of {", ".join(sorted(FRESHNESS_STATUSES))}')
    if sort not in SORT_OPTIONS:
        raise HTTPException(422, f'Sort must be one of {", ".join(sorted(SORT_OPTIONS))}')

    query = (
        select(Listing)
        .options(joinedload(Listing.farmer), joinedload(Listing.category))
        .where(Listing.status == 'active')
    )
    if category_id is not None:
        query = query.where(Listing.category_id == category_id)
    if min_price is not None:
        query = query.where(Listing.price_per_unit >= min_price)
    if max_price is not None:
        query = query.where(Listing.price_per_unit <= max_price)
    if organic is not None:
        query = query.where(Listing.organic == organic)
    if bulk_available is not None:
        query = query.where(Listing.bulk_available == bulk_available)
    if location:
        query = query.where(func.lower(Listing.location_text).like(f'%{location.lower()}%'))
    if farmer:
        query = query.join(User, Listing.farmer_id == User.id).where(
            func.lower(User.name).like(f'%{farmer.lower()}%')
        )

    rows = db.scalars(query).unique().all()

    now = datetime.utcnow()
    needle = q.lower() if q else None
    has_origin = lat is not None and lng is not None

    prepared = []
    for x in rows:
        status, hours = freshness(x, now)
        if status == 'Expired':
            continue
        if freshness_status and status != freshness_status:
            continue
        if needle and needle not in x.title.lower() and needle not in x.location_text.lower():
            continue
        distance = None
        if has_origin and x.latitude is not None and x.longitude is not None:
            distance = haversine_km(lat, lng, x.latitude, x.longitude)
        prepared.append((x, status, hours, distance))

    if sort == 'price_asc':
        prepared.sort(key=lambda t: t[0].price_per_unit)
    elif sort == 'price_desc':
        prepared.sort(key=lambda t: t[0].price_per_unit, reverse=True)
    elif sort == 'newest':
        prepared.sort(key=lambda t: t[0].listing_time, reverse=True)
    elif sort == 'nearest':
        if not has_origin:
            raise HTTPException(422, 'Sorting by distance needs lat and lng')
        prepared.sort(key=lambda t: (t[3] is None, t[3] if t[3] is not None else 0.0))
    else:
        prepared.sort(key=lambda t: t[2], reverse=True)

    total = len(prepared)
    pages = max(1, math.ceil(total / page_size))
    current = min(page, pages)
    start = (current - 1) * page_size
    window = prepared[start:start + page_size]

    return {
        'items': [listing_out(x, status, hours, distance) for x, status, hours, distance in window],
        'total': total,
        'page': current,
        'pages': pages,
        'page_size': page_size,
    }
@router.get('/farmer/listings')
def farmer_listings(user:User=Depends(require_roles('farmer')),db:Session=Depends(get_db)):
    """Every listing this farmer owns, whatever its status.

    The public /listings endpoint filters to active and non-expired, so a
    farmer cannot see their own suspended or expired stock through it. This is
    the view the edit and remove controls hang off, and it is the one place a
    farmer learns why an admin suspended something.
    """
    rows=db.scalars(
        select(Listing)
        .options(joinedload(Listing.farmer),joinedload(Listing.category))
        .where(Listing.farmer_id==user.id)
        .order_by(Listing.listing_time.desc())
    ).unique().all()
    return [listing_out(x, include_moderation=True) for x in rows]
@router.get('/listings/{listing_id}')
def listing(listing_id:int,viewer:User|None=Depends(optional_user),db:Session=Depends(get_db)):
    """One listing, from the public marketplace or the owner's own view.

    Anonymous callers and other buyers only reach active listings. The owning
    farmer and admins reach it in any state, which is what the edit page and
    the moderation screens need — a suspended listing that 404s for its owner
    could never be corrected.
    """
    x=db.scalar(select(Listing).options(joinedload(Listing.farmer),joinedload(Listing.category)).where(Listing.id==listing_id))
    if not x: raise HTTPException(404,'Listing not found')
    privileged=viewer is not None and (viewer.id==x.farmer_id or viewer.role=='admin')
    if x.status!='active' and not privileged:
        raise HTTPException(404,'Listing not found')
    return listing_out(x, include_moderation=privileged)
@router.post('/listings')
def create_listing(data:ListingCreate,user:User=Depends(require_roles('farmer')),db:Session=Depends(get_db)):
    if data.harvest_time and data.harvest_time>datetime.utcnow(): raise HTTPException(422,'Harvest time cannot be in the future')
    category=db.get(Category,data.category_id)
    if not category: raise HTTPException(404,'Category not found')

    # A farmer carrying enough distinct reports loses control of lifespan_hours.
    report_count=db.scalar(select(func.count()).select_from(Report).where(Report.reported_user_id==user.id)) or 0
    lifespan=data.lifespan_hours
    if report_count>=get_settings().report_lock_threshold:
        lifespan=category.default_lifespan_hours

    payload=data.model_dump()
    payload['lifespan_hours']=lifespan
    base=data.harvest_time or datetime.utcnow()
    payload['expires_at']=base+timedelta(hours=lifespan)
    x=Listing(farmer_id=user.id,**payload);db.add(x);db.commit();db.refresh(x)
    return {'id':x.id,'lifespan_hours':x.lifespan_hours,'expires_at':x.expires_at.isoformat()}
@router.patch('/listings/{listing_id}')
def update_listing(listing_id:int,data:ListingUpdate,user:User=Depends(require_roles('farmer')),db:Session=Depends(get_db)):
    """Edit one of this farmer's own listings.

    `expires_at` is recomputed unconditionally. Recomputing when nothing that
    feeds it changed produces the same value, so the branch that would decide
    "did harvest_time or lifespan_hours move?" is not worth its own bug surface.
    Leaving it stale was the correctness gap dispatch #10 flagged.

    The report lock applies here too. Without it a locked farmer could edit
    their way around the lifespan cap that create_listing enforces.
    """
    x=db.get(Listing,listing_id)
    if not x: raise HTTPException(404,'Listing not found')
    if x.farmer_id!=user.id: raise HTTPException(403,'This is not your listing')
    if x.status=='removed': raise HTTPException(409,'A removed listing cannot be edited')

    payload=data.model_dump(exclude_unset=True)
    old_image=x.image_url

    if 'category_id' in payload and payload['category_id'] is not None:
        if not db.get(Category,payload['category_id']): raise HTTPException(404,'Category not found')

    for field,value in payload.items():
        setattr(x,field,value)

    if x.harvest_time and x.harvest_time>datetime.utcnow():
        raise HTTPException(422,'Harvest time cannot be in the future')

    category=db.get(Category,x.category_id)
    report_count=db.scalar(select(func.count()).select_from(Report).where(Report.reported_user_id==user.id)) or 0
    locked=report_count>=get_settings().report_lock_threshold
    if locked:
        x.lifespan_hours=category.default_lifespan_hours

    base=x.harvest_time or x.listing_time
    x.expires_at=base+timedelta(hours=x.lifespan_hours)
    db.commit();db.refresh(x)

    if old_image!=x.image_url:
        _delete_orphaned_upload(db,old_image)

    return {
        'id':x.id,
        'lifespan_hours':x.lifespan_hours,
        'lifespan_locked':locked,
        'expires_at':x.expires_at.isoformat(),
    }
@router.delete('/listings/{listing_id}')
def delete_listing(
    listing_id:int,
    cancel_open_orders:bool=False,
    user:User=Depends(require_roles('farmer')),
    db:Session=Depends(get_db),
):
    """Remove one of this farmer's own listings.

    Soft delete — the row is retained with status 'removed' so order history
    still resolves. That matches what the admin flow in dispatch #9 does, and
    it means the listing can be restored.

    Because the row is retained, the uploaded image is deliberately NOT deleted.
    Restoring a listing whose photo had been removed would leave a broken card.
    Image cleanup happens on replacement instead — see update_listing.

    Open orders block the removal unless cancel_open_orders is set, the same
    shape the admin endpoint uses. Cancelling restores the reserved stock.
    """
    x=db.get(Listing,listing_id)
    if not x: raise HTTPException(404,'Listing not found')
    if x.farmer_id!=user.id: raise HTTPException(403,'This is not your listing')
    if x.status=='removed': raise HTTPException(409,'That listing is already removed')

    open_orders=db.scalars(select(Order).where(Order.listing_id==listing_id,Order.status.in_(OPEN_ORDER_STATUSES))).all()
    if open_orders and not cancel_open_orders:
        raise HTTPException(409,f'This listing has {len(open_orders)} open {"order" if len(open_orders)==1 else "orders"}. Confirm to cancel them and restore their reserved stock.')

    cancelled=0
    if open_orders:
        now=datetime.utcnow()
        for o in open_orders:
            x.available_quantity+=o.quantity
            o.status='cancelled'
            o.status_changed_at=now
            if o.delivery_method=='delivery' and o.delivery_status not in CLOSED_DELIVERY_STATUSES:
                o.delivery_status='failed'
                o.delivery_note='Listing removed by the farmer'
            cancelled+=1

    x.status='removed'
    x.moderation_note='Removed by the farmer'
    x.suspended_by_deactivation=False
    db.commit()
    return {'id':x.id,'status':x.status,'cancelled_orders':cancelled}

# ---------------------------------------------------------------------------
# Image upload
# ---------------------------------------------------------------------------
@router.post('/uploads')
async def upload_image(file:UploadFile=File(...),user:User=Depends(require_roles('farmer'))):
    """Store a listing photo and return its public path.

    Two independent checks: the declared content type must be one of the three
    accepted, and the actual bytes must match it. Without the second check a
    file named .jpg containing anything at all would be stored and later served
    back with an image content type.

    The stored name is a UUID plus an extension derived from the content type.
    The client's filename is discarded entirely, so path traversal is impossible.
    """
    extension=ALLOWED_IMAGE_TYPES.get(file.content_type or '')
    if extension is None:
        raise HTTPException(422,'Images must be JPEG, PNG, or WebP')
    data=await file.read()
    if not data:
        raise HTTPException(422,'The uploaded file was empty')
    if len(data)>MAX_IMAGE_BYTES:
        raise HTTPException(422,f'Images must be 10 MB or smaller. That file is {len(data)/1024/1024:.1f} MB.')

    sniffed=sniff_image_type(data)
    if sniffed is None:
        raise HTTPException(422,'That file does not look like an image')
    if sniffed!=file.content_type:
        raise HTTPException(422,f'That file is {sniffed}, not {file.content_type}')

    UPLOAD_DIR.mkdir(parents=True,exist_ok=True)
    name=f'{uuid.uuid4().hex}{extension}'
    (UPLOAD_DIR/name).write_bytes(data)
    return {'url':f'/uploads/{name}','bytes':len(data)}

# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
@router.post('/reports')
def create_report(data:ReportInput,user:User=Depends(current_user),db:Session=Depends(get_db)):
    x=db.get(Listing,data.listing_id)
    if not x: raise HTTPException(404,'Listing not found')
    if x.farmer_id==user.id: raise HTTPException(422,'You cannot report your own listing')
    already=db.scalar(select(Report).where(Report.reporter_id==user.id,Report.listing_id==x.id))
    if already: raise HTTPException(409,'You have already reported this listing')
    r=Report(reporter_id=user.id,reported_user_id=x.farmer_id,listing_id=x.id,reason=data.reason,details=data.details)
    db.add(r);db.commit();db.refresh(r)
    return {'id':r.id,'status':r.status}
@router.get('/reports')
def list_reports(status:str|None=None,user:User=Depends(require_roles('admin')),db:Session=Depends(get_db)):
    query=select(Report,User.name,Listing.title).join(User,Report.reporter_id==User.id).join(Listing,Report.listing_id==Listing.id)
    if status: query=query.where(Report.status==status)
    rows=db.execute(query.order_by(Report.created_at.desc())).all()
    out=[]
    for r,reporter_name,listing_title in rows:
        reported=db.get(User,r.reported_user_id)
        out.append(report_out(r,reporter_name,reported.name if reported else 'Unknown',listing_title))
    return out
@router.patch('/admin/reports/{report_id}')
def admin_resolve_report(report_id:int,data:ReportResolveInput,user:User=Depends(require_roles('admin')),db:Session=Depends(get_db)):
    """Close a report as resolved or dismissed.

    Only an admin, and only from 'open'. Closing is one-way — there is no
    reopen, because a report that was acted on and then reopened would muddy
    what `reports_open` in the metrics means.

    Resolving does NOT change the reported listing or the reported user. It
    records that an admin looked. Any action taken is separate.
    """
    r=db.get(Report,report_id)
    if not r: raise HTTPException(404,'Report not found')
    if r.status!='open': raise HTTPException(409,f'That report is already {r.status}')
    r.status=data.status
    r.resolution_note=data.note
    db.commit()
    return {'id':r.id,'status':r.status,'resolution_note':r.resolution_note}
@router.get('/reports/against-me')
def reports_against_me(user:User=Depends(current_user),db:Session=Depends(get_db)):
    count=db.scalar(select(func.count()).select_from(Report).where(Report.reported_user_id==user.id)) or 0
    threshold=get_settings().report_lock_threshold
    return {'count':count,'threshold':threshold,'locked':count>=threshold}

# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------
def _pick_cycle_listing(db:Session,sub:Subscription,now:datetime)->Listing|None:
    rows=db.scalars(
        select(Listing).where(
            Listing.farmer_id==sub.farmer_id,
            Listing.category_id==sub.category_id,
            Listing.status=='active',
            Listing.unit==sub.unit,
        )
    ).all()
    best=None
    for x in rows:
        status,hours=freshness(x,now)
        if status=='Expired':
            continue
        if x.available_quantity<sub.quantity:
            continue
        if best is None or hours>best[1]:
            best=(x,hours)
    return best[0] if best else None
@router.post('/subscriptions/generate-due')
def generate_due_cycles(user:User=Depends(current_user),db:Session=Depends(get_db)):
    now=datetime.utcnow()
    if user.role=='farmer':
        due=db.scalars(select(Subscription).where(
            Subscription.farmer_id==user.id,
            Subscription.status=='active',
            Subscription.next_cycle_at<=now,
        )).all()
    else:
        due=db.scalars(select(Subscription).where(
            Subscription.buyer_id==user.id,
            Subscription.status=='active',
            Subscription.next_cycle_at<=now,
        )).all()

    generated=0
    skipped=0
    try:
        for sub in due:
            while sub.next_cycle_at<=now:
                scheduled=sub.next_cycle_at
                following=scheduled+timedelta(days=sub.frequency_days)

                if following<=now:
                    db.add(SubscriptionCycle(
                        subscription_id=sub.id,
                        scheduled_for=scheduled,
                        status='skipped',
                        reason='Missed — the subscriptions page was not opened in time',
                    ))
                    skipped+=1
                    sub.next_cycle_at=following
                    continue

                if sub.delivery_latitude is None or sub.delivery_longitude is None:
                    # Subscriptions created before the pin rule existed. Their
                    # cycles cannot become a routable order, so they are
                    # recorded as skipped rather than generating a delivery the
                    # farmer can never finish.
                    db.add(SubscriptionCycle(
                        subscription_id=sub.id,
                        scheduled_for=scheduled,
                        status='skipped',
                        reason='This subscription has no delivery pin, so no order could be placed. Set up a new one with a pinned address.',
                    ))
                    skipped+=1
                    sub.next_cycle_at=following
                    continue

                category=db.get(Category,sub.category_id)
                label=category.name if category else 'produce'
                listing=_pick_cycle_listing(db,sub,now)
                if listing is None:
                    db.add(SubscriptionCycle(
                        subscription_id=sub.id,
                        scheduled_for=scheduled,
                        status='skipped',
                        reason=f'No {label} in {sub.unit} was available that week',
                    ))
                    skipped+=1
                else:
                    try:
                        _reserve_stock(db,listing,sub.quantity)
                    except HTTPException:
                        # Stock moved between picking the listing and reserving
                        # it. Skip the cycle rather than generate an order
                        # against stock that is no longer there.
                        db.add(SubscriptionCycle(
                            subscription_id=sub.id,
                            scheduled_for=scheduled,
                            status='skipped',
                            reason=f'No {label} in {sub.unit} was available that week',
                        ))
                        skipped+=1
                        sub.next_cycle_at=following
                        continue

                    order=Order(
                        buyer_id=sub.buyer_id,
                        farmer_id=sub.farmer_id,
                        listing_id=listing.id,
                        subscription_id=sub.id,
                        quantity=sub.quantity,
                        total_amount=sub.quantity*listing.price_per_unit,
                        payment_mode='subscription',
                        payment_label=sub.payment_label,
                        status='requested',
                        status_changed_at=now,
                        **_delivery_fields('delivery',sub.delivery_address,sub.delivery_latitude,sub.delivery_longitude),
                    )
                    db.add(order)
                    db.flush()
                    db.add(SubscriptionCycle(
                        subscription_id=sub.id,
                        scheduled_for=scheduled,
                        status='generated',
                        order_id=order.id,
                    ))
                    generated+=1
                sub.next_cycle_at=following
        db.commit()
    except IntegrityError:
        db.rollback()
        return {'generated':0,'skipped':0,'raced':True}
    return {'generated':generated,'skipped':skipped,'raced':False}
@router.get('/subscriptions')
def list_subscriptions(user:User=Depends(current_user),db:Session=Depends(get_db)):
    if user.role=='farmer':
        rows=db.scalars(
            select(Subscription)
            .options(joinedload(Subscription.category))
            .where(Subscription.farmer_id==user.id)
            .order_by(Subscription.created_at.desc())
        ).unique().all()
    else:
        rows=db.scalars(
            select(Subscription)
            .options(joinedload(Subscription.category))
            .where(Subscription.buyer_id==user.id)
            .order_by(Subscription.created_at.desc())
        ).unique().all()

    if not rows:
        return []

    ids=[s.id for s in rows]
    all_cycles=db.scalars(
        select(SubscriptionCycle)
        .where(SubscriptionCycle.subscription_id.in_(ids))
        .order_by(SubscriptionCycle.scheduled_for.desc())
    ).all()
    by_sub={}
    for c in all_cycles:
        bucket=by_sub.setdefault(c.subscription_id,[])
        if len(bucket)<RECENT_CYCLES:
            bucket.append(c)

    out=[]
    for s in rows:
        buyer=db.get(User,s.buyer_id)
        farmer=db.get(User,s.farmer_id)
        out.append(subscription_out(
            s,
            buyer.name if buyer else 'Unknown',
            farmer.name if farmer else 'Unknown',
            by_sub.get(s.id,[]),
        ))
    return out
@router.post('/subscriptions')
def create_subscription(data:SubscriptionInput,user:User=Depends(require_roles('buyer')),db:Session=Depends(get_db)):
    farmer=db.get(User,data.farmer_id)
    if not farmer or farmer.role!='farmer': raise HTTPException(404,'Farmer not found')
    if farmer.id==user.id: raise HTTPException(422,'You cannot subscribe to yourself')
    if not farmer.is_active: raise HTTPException(422,'That farmer is not currently active')
    if not db.get(Category,data.category_id): raise HTTPException(404,'Category not found')
    # Every subscription is a delivery, and a delivery without a pin has no
    # fulfilment path — the generated order could never be routed or completed.
    if data.delivery_latitude is None or data.delivery_longitude is None:
        raise HTTPException(422,'A subscription needs a pinned delivery address, because every cycle is delivered. Add a map pin to your address first.')

    now=datetime.utcnow()
    s=Subscription(
        buyer_id=user.id,
        farmer_id=farmer.id,
        category_id=data.category_id,
        quantity=data.quantity,
        unit=data.unit,
        frequency_days=data.frequency_days,
        status='active',
        next_cycle_at=now+timedelta(days=data.frequency_days),
        delivery_address=data.delivery_address,
        delivery_latitude=data.delivery_latitude,
        delivery_longitude=data.delivery_longitude,
        payment_label=data.payment_label,
    )
    db.add(s);db.commit();db.refresh(s)
    return {'id':s.id,'next_cycle_at':s.next_cycle_at.isoformat()}
@router.delete('/admin/subscriptions/{subscription_id}')
def admin_cancel_subscription(subscription_id:int,user:User=Depends(require_roles('admin')),db:Session=Depends(get_db)):
    s=db.get(Subscription,subscription_id)
    if not s: raise HTTPException(404,'Subscription not found')
    if s.status=='cancelled': raise HTTPException(409,'That subscription is already cancelled')
    s.status='cancelled'
    s.cancelled_at=datetime.utcnow()
    db.commit()
    return {'id':s.id,'status':s.status,'cancelled_at':s.cancelled_at.isoformat()}
@router.get('/admin/subscriptions')
def admin_list_subscriptions(user:User=Depends(require_roles('admin')),db:Session=Depends(get_db)):
    rows=db.scalars(
        select(Subscription)
        .options(joinedload(Subscription.category))
        .order_by(Subscription.created_at.desc())
    ).unique().all()
    out=[]
    for s in rows:
        buyer=db.get(User,s.buyer_id)
        farmer=db.get(User,s.farmer_id)
        out.append(subscription_out(
            s,
            buyer.name if buyer else 'Unknown',
            farmer.name if farmer else 'Unknown',
            [],
        ))
    return out

# ---------------------------------------------------------------------------
# Deliveries
# ---------------------------------------------------------------------------
@router.get('/farmer/deliveries')
def farmer_deliveries(user:User=Depends(require_roles('farmer')),db:Session=Depends(get_db)):
    rows=db.execute(
        select(Order,Listing.title,User.name)
        .join(Listing,Order.listing_id==Listing.id)
        .join(User,Order.buyer_id==User.id)
        .where(
            Order.farmer_id==user.id,
            Order.status=='accepted',
            Order.delivery_method=='delivery',
            Order.delivery_status.notin_(CLOSED_DELIVERY_STATUSES),
        )
        .order_by(Order.created_at.asc())
    ).all()

    located=[]
    unroutable=[]
    for o,title,buyer_name in rows:
        entry={
            'order_id':o.id,
            'listing_title':title,
            'buyer_name':buyer_name,
            'address':o.delivery_address or '',
            'quantity':o.quantity,
            'delivery_status':o.delivery_status,
            'delivery_note':o.delivery_note,
            'created_at':o.created_at.isoformat(),
        }
        if o.delivery_latitude is None or o.delivery_longitude is None:
            unroutable.append(entry)
        else:
            entry['latitude']=o.delivery_latitude
            entry['longitude']=o.delivery_longitude
            located.append(entry)

    origin=_farmer_origin(db,user.id)
    if origin is None:
        return {
            'origin':None,
            'stops':[],
            'unroutable':located+unroutable,
            'total_distance_km':None,
            'note':'Add coordinates to one of your listings to get a suggested route.',
        }

    if not located:
        return {
            'origin':{'latitude':origin[0],'longitude':origin[1]},
            'stops':[],
            'unroutable':unroutable,
            'total_distance_km':0.0,
            'note':None,
        }

    ordered,total=_suggest_route(origin,located)
    for stop in ordered:
        stop['distance_from_origin_km']=round(haversine_km(origin[0],origin[1],stop['latitude'],stop['longitude']),1)

    return {
        'origin':{'latitude':origin[0],'longitude':origin[1]},
        'stops':ordered,
        'unroutable':unroutable,
        'total_distance_km':round(total,1),
        'note':None,
    }
@router.patch('/orders/{order_id}/delivery-status')
def update_delivery_status(order_id:int,data:DeliveryStatusInput,user:User=Depends(current_user),db:Session=Depends(get_db)):
    order=db.get(Order,order_id)
    if not order: raise HTTPException(404,'Order not found')

    is_farmer=user.role=='farmer' and order.farmer_id==user.id
    is_admin=user.role=='admin'
    if not (is_farmer or is_admin): raise HTTPException(403,'Only the farmer or an admin can update a delivery')

    if order.delivery_method!='delivery':
        raise HTTPException(422,'This order is for pickup, so it has no delivery status')
    if order.status!='accepted':
        raise HTTPException(409,f'An order must be accepted before it can be delivered. This one is {order.status}.')
    if data.status not in DELIVERY_STATUSES:
        raise HTTPException(422,f'Delivery status must be one of {", ".join(sorted(DELIVERY_STATUSES))}')

    allowed=DELIVERY_TRANSITIONS.get(order.delivery_status,set())
    if data.status not in allowed:
        raise HTTPException(409,f'A delivery that is {order.delivery_status} cannot be moved to {data.status}')

    order.delivery_status=data.status
    order.delivery_note=data.note if data.status=='failed' else None
    db.commit()
    return {'id':order.id,'delivery_status':order.delivery_status,'delivery_note':order.delivery_note}

# ---------------------------------------------------------------------------
# Demand forecasting
# ---------------------------------------------------------------------------
@router.get('/forecast')
def forecast(user:User=Depends(require_roles('farmer')),db:Session=Depends(get_db)):
    """Rolling-average demand forecast for this farmer's own produce.

    Scoped to orders placed with THIS farmer. Grouped by category, location, and
    unit. The unit matters: summing kilograms and dozens into one total would
    produce a figure that is not a quantity of anything.

    Demand counts every order placed, including ones never answered. Only
    rejected and cancelled orders are excluded.

    With only a handful of orders this is close to a restatement of the raw data
    rather than a prediction. `has_enough_data` flags that.
    """
    now=datetime.utcnow()
    window_start=now-timedelta(weeks=FORECAST_WINDOW_WEEKS)
    midpoint=now-timedelta(weeks=FORECAST_WINDOW_WEEKS//2)

    rows=db.execute(
        select(Order,Listing,Category)
        .join(Listing,Order.listing_id==Listing.id)
        .join(Category,Listing.category_id==Category.id)
        .where(
            Order.farmer_id==user.id,
            Order.status.in_(DEMAND_ORDER_STATUSES),
            Order.created_at>=window_start,
        )
    ).all()

    groups={}
    for o,listing,category in rows:
        location=(listing.location_text or '').strip() or 'Unspecified'
        key=(category.id,category.name,location,listing.unit)
        bucket=groups.setdefault(key,{
            'order_count':0,
            'total_quantity':0.0,
            'recent_quantity':0.0,
            'prior_quantity':0.0,
        })
        bucket['order_count']+=1
        bucket['total_quantity']+=o.quantity
        if o.created_at>=midpoint:
            bucket['recent_quantity']+=o.quantity
        else:
            bucket['prior_quantity']+=o.quantity

    items=[]
    for (category_id,category_name,location,unit),b in groups.items():
        total=b['total_quantity']
        weekly_rate=total/FORECAST_WINDOW_WEEKS
        recent=b['recent_quantity']
        prior=b['prior_quantity']

        if prior==0 and recent>0:
            trend='rising'
            trend_pct=None
        elif prior==0 and recent==0:
            trend='steady'
            trend_pct=0.0
        else:
            change=((recent-prior)/prior)*100.0
            trend_pct=round(change,1)
            if change>TREND_THRESHOLD_PCT:
                trend='rising'
            elif change<-TREND_THRESHOLD_PCT:
                trend='falling'
            else:
                trend='steady'

        items.append({
            'category_id':category_id,
            'category':category_name,
            'location':location,
            'unit':unit,
            'order_count':b['order_count'],
            'past_quantity':round(total,2),
            'weekly_rate':round(weekly_rate,2),
            'forecast_quantity':round(weekly_rate*FORECAST_HORIZON_WEEKS,2),
            'recent_quantity':round(recent,2),
            'prior_quantity':round(prior,2),
            'trend':trend,
            'trend_pct':trend_pct,
            'has_enough_data':b['order_count']>=FORECAST_MIN_ORDERS,
        })

    items.sort(key=lambda i:i['forecast_quantity'],reverse=True)

    note=None
    if not rows:
        note=(
            f'No orders in the last {FORECAST_WINDOW_WEEKS} weeks, so there is '
            'nothing to forecast yet.'
        )
    elif len(rows)<FORECAST_MIN_ORDERS:
        note=(
            f'Only {len(rows)} order{"s" if len(rows)!=1 else ""} in the last '
            f'{FORECAST_WINDOW_WEEKS} weeks. Treat this as a summary of what '
            'happened, not a prediction of what will.'
        )

    return {
        'window_weeks':FORECAST_WINDOW_WEEKS,
        'forecast_weeks':FORECAST_HORIZON_WEEKS,
        'window_start':window_start.isoformat(),
        'generated_at':now.isoformat(),
        'order_count':len(rows),
        'items':items,
        'note':note,
    }

# ---------------------------------------------------------------------------
# Admin — users
# ---------------------------------------------------------------------------
@router.get('/admin/users')
def admin_list_users(user:User=Depends(require_roles('admin')),db:Session=Depends(get_db)):
    rows=db.scalars(select(User).order_by(User.created_at.desc())).all()
    out=[]
    for u in rows:
        listing_count=db.scalar(select(func.count()).select_from(Listing).where(Listing.farmer_id==u.id)) or 0
        report_count=db.scalar(select(func.count()).select_from(Report).where(Report.reported_user_id==u.id)) or 0
        out.append({
            'id':u.id,'name':u.name,'email':u.email,'role':u.role,'is_active':u.is_active,
            'verification_status':u.verification_status,
            'created_at':u.created_at.isoformat(),'listing_count':listing_count,'report_count':report_count,
        })
    return out
@router.patch('/admin/users/{user_id}/active')
def admin_set_user_active(user_id:int,data:UserActiveInput,user:User=Depends(require_roles('admin')),db:Session=Depends(get_db)):
    """Activate or deactivate an account.

    Deactivating a farmer also suspends their active listings, so buyers cannot
    order produce nobody will fulfil. The listings are flagged so reactivation
    restores exactly those, leaving anything an admin suspended by hand alone.

    Admin accounts are protected and an admin cannot change their own status.
    Neither is recoverable through the UI: a deactivated admin cannot sign in to
    reactivate anyone.
    """
    target=db.get(User,user_id)
    if not target: raise HTTPException(404,'User not found')
    if target.id==user.id: raise HTTPException(422,'You cannot change your own active status')
    if target.role=='admin': raise HTTPException(422,'Admin accounts cannot be deactivated')

    target.is_active=data.is_active
    affected=0

    if not data.is_active:
        # Suspend only what is currently live. Already-suspended and removed
        # listings are left exactly as they are.
        own=db.scalars(select(Listing).where(Listing.farmer_id==target.id,Listing.status=='active')).all()
        for x in own:
            x.status='suspended'
            x.suspended_by_deactivation=True
            affected+=1
    else:
        # Restore only what the deactivation suspended.
        restored=db.scalars(select(Listing).where(Listing.farmer_id==target.id,Listing.suspended_by_deactivation==True)).all()
        for x in restored:
            x.status='active'
            x.suspended_by_deactivation=False
            affected+=1

    db.commit()
    return {'id':target.id,'is_active':target.is_active,'listings_affected':affected}

@router.patch('/admin/users/{user_id}/verification')
def admin_set_user_verification(
    user_id:int,
    data:AdminVerificationInput,
    user:User=Depends(require_roles('admin')),
    db:Session=Depends(get_db),
):
    """Grant or withdraw the verified badge on a farmer account.

    Only farmers can be verified. The badge is a claim about a seller and
    it renders on their listings, so a verified buyer would carry a status
    nothing displays and a verified admin would be attesting to their own
    account. Both are refused rather than silently accepted.

    This is separate from /active on purpose. Deactivating a farmer
    suspends their listings; it does not revoke a verification an admin
    granted, and reactivating them does not restore one that was
    withdrawn. The two are independent decisions.
    """
    target=db.get(User,user_id)
    if not target: raise HTTPException(404,'User not found')
    if target.role!='farmer':
        raise HTTPException(422,'Only farmer accounts can be verified')
    target.verification_status=data.verification_status
    db.commit()
    return {'id':target.id,'verification_status':target.verification_status}

# ---------------------------------------------------------------------------
# Admin — listings
# ---------------------------------------------------------------------------
@router.get('/admin/listings')
def admin_list_listings(status:str|None=None,user:User=Depends(require_roles('admin')),db:Session=Depends(get_db)):
    query=select(Listing).options(joinedload(Listing.farmer),joinedload(Listing.category))
    if status: query=query.where(Listing.status==status)
    rows=db.scalars(query.order_by(Listing.listing_time.desc())).unique().all()
    counts=dict(db.execute(
        select(Order.listing_id,func.count())
        .where(Order.status.in_(OPEN_ORDER_STATUSES))
        .group_by(Order.listing_id)
    ).all())
    return [{
        'id':x.id,'title':x.title,'category':x.category.name,'farmer_name':x.farmer.name,
        'price_per_unit':x.price_per_unit,'unit':x.unit,'available_quantity':x.available_quantity,
        'location':x.location_text,'status':x.status,'moderation_note':x.moderation_note,
        'image_url':x.image_url,'open_orders':counts.get(x.id,0),
        'listing_time':x.listing_time.isoformat(),
    } for x in rows]
@router.patch('/admin/listings/{listing_id}/status')
def admin_set_listing_status(
    listing_id:int,
    data:AdminListingStatusInput,
    user:User=Depends(require_roles('admin')),
    db:Session=Depends(get_db),
):
    x=db.get(Listing,listing_id)
    if not x: raise HTTPException(404,'Listing not found')
    if data.status not in LISTING_MODERATION_STATUSES:
        raise HTTPException(422,'Status must be active, suspended, or removed')

    # Removal is permanent. The row is kept so order history still resolves, but
    # nothing puts it back on the marketplace — otherwise 'removed' would just
    # be a slower kind of suspension and the distinction would mean nothing.
    if x.status=='removed' and data.status!='removed':
        raise HTTPException(409,'A removed listing cannot be restored')

    # Activating a listing whose farmer cannot sign in would put produce on the
    # marketplace that nobody can fulfil.
    if data.status=='active':
        owner=db.get(User,x.farmer_id)
        if owner is not None and not owner.is_active:
            raise HTTPException(409,'That listing belongs to a deactivated farmer, so it cannot be made active')

    open_orders=db.scalars(select(Order).where(Order.listing_id==listing_id,Order.status.in_(OPEN_ORDER_STATUSES))).all()

    if data.status=='removed' and open_orders and not data.cancel_open_orders:
        raise HTTPException(409,f'This listing has {len(open_orders)} open {"order" if len(open_orders)==1 else "orders"}. Confirm to cancel them and restore their reserved stock.')

    cancelled=0
    if data.status=='removed' and open_orders and data.cancel_open_orders:
        now=datetime.utcnow()
        for o in open_orders:
            x.available_quantity+=o.quantity
            o.status='cancelled'
            o.status_changed_at=now
            if o.delivery_method=='delivery' and o.delivery_status not in CLOSED_DELIVERY_STATUSES:
                o.delivery_status='failed'
                o.delivery_note='Listing removed by an admin'
            cancelled+=1

    x.status=data.status
    # A manual decision overrides the deactivation cascade. Without this, an
    # admin who suspends an already-auto-suspended listing would find it
    # silently restored the next time the farmer was reactivated.
    x.suspended_by_deactivation=False
    if data.moderation_note is not None:
        x.moderation_note=data.moderation_note
    db.commit()
    return {'id':x.id,'status':x.status,'moderation_note':x.moderation_note,'cancelled_orders':cancelled}

# ---------------------------------------------------------------------------
# Admin — orders
# ---------------------------------------------------------------------------
@router.get('/admin/orders')
def admin_list_orders(user:User=Depends(require_roles('admin')),db:Session=Depends(get_db)):
    """Every order on the platform, newest first.

    Admins could already transition any order through
    PATCH /orders/{id}/status — update_order_status permits it — but there was
    no list to act on. This is that list.

    No pagination. Every order loads at once, which is fine at demo scale and
    is not fine beyond it.
    """
    buyer=aliased(User)
    farmer=aliased(User)
    rows=db.execute(
        select(Order,Listing.title,buyer.name,farmer.name)
        .join(Listing,Order.listing_id==Listing.id)
        .join(buyer,Order.buyer_id==buyer.id)
        .join(farmer,Order.farmer_id==farmer.id)
        .order_by(Order.created_at.desc())
    ).all()
    out=[]
    for o,title,buyer_name,farmer_name in rows:
        entry=order_out(o,title,buyer_name)
        entry['farmer_name']=farmer_name
        out.append(entry)
    return out

# ---------------------------------------------------------------------------
# Admin — categories
# ---------------------------------------------------------------------------
@router.post('/admin/categories')
def admin_create_category(data:CategoryInput,user:User=Depends(require_roles('admin')),db:Session=Depends(get_db)):
    if db.scalar(select(Category).where(Category.name==data.name)):
        raise HTTPException(409,'A category with that name already exists')
    c=Category(name=data.name,default_lifespan_hours=data.default_lifespan_hours)
    db.add(c);db.commit();db.refresh(c)
    return {'id':c.id,'name':c.name,'default_lifespan_hours':c.default_lifespan_hours}
@router.patch('/admin/categories/{category_id}')
def admin_update_category(category_id:int,data:CategoryUpdateInput,user:User=Depends(require_roles('admin')),db:Session=Depends(get_db)):
    c=db.get(Category,category_id)
    if not c: raise HTTPException(404,'Category not found')
    if data.name is not None and data.name!=c.name:
        if db.scalar(select(Category).where(Category.name==data.name)):
            raise HTTPException(409,'A category with that name already exists')
        c.name=data.name
    if data.default_lifespan_hours is not None:
        c.default_lifespan_hours=data.default_lifespan_hours
    db.commit()
    return {'id':c.id,'name':c.name,'default_lifespan_hours':c.default_lifespan_hours}
@router.delete('/admin/categories/{category_id}')
def admin_delete_category(category_id:int,user:User=Depends(require_roles('admin')),db:Session=Depends(get_db)):
    c=db.get(Category,category_id)
    if not c: raise HTTPException(404,'Category not found')
    in_use=db.scalar(select(func.count()).select_from(Listing).where(Listing.category_id==category_id)) or 0
    if in_use:
        raise HTTPException(409,f'This category is used by {in_use} {"listing" if in_use==1 else "listings"}. Move them to another category before deleting.')
    db.delete(c);db.commit()
    return {'ok':True}

# ---------------------------------------------------------------------------
# Admin — metrics
# ---------------------------------------------------------------------------
@router.get('/admin/metrics')
def metrics(user:User=Depends(require_roles('admin')),db:Session=Depends(get_db)):
    return {
        'users':db.scalar(select(func.count()).select_from(User)) or 0,
        'listings':db.scalar(select(func.count()).select_from(Listing)) or 0,
        'orders':db.scalar(select(func.count()).select_from(Order)) or 0,
        'reports_open':db.scalar(select(func.count()).select_from(Report).where(Report.status=='open')) or 0,
        'categories':db.scalar(select(func.count()).select_from(Category)) or 0,
        'subscriptions':db.scalar(select(func.count()).select_from(Subscription).where(Subscription.status=='active')) or 0,
        'deliveries_open':db.scalar(select(func.count()).select_from(Order).where(
            Order.delivery_method=='delivery',
            Order.delivery_status.notin_(CLOSED_DELIVERY_STATUSES),
        )) or 0,
    }

# ---------------------------------------------------------------------------
# Saved addresses
# ---------------------------------------------------------------------------
@router.get('/addresses')
def list_addresses(user:User=Depends(current_user),db:Session=Depends(get_db)):
    rows=db.scalars(select(Address).where(Address.user_id==user.id).order_by(Address.is_default.desc(),Address.created_at.desc())).all()
    return [address_out(a) for a in rows]
@router.post('/addresses')
def create_address(data:AddressInput,user:User=Depends(current_user),db:Session=Depends(get_db)):
    existing=db.scalar(select(func.count()).select_from(Address).where(Address.user_id==user.id)) or 0
    make_default=data.is_default or existing==0
    if make_default:
        for a in db.scalars(select(Address).where(Address.user_id==user.id)).all(): a.is_default=False
    a=Address(
        user_id=user.id,label=data.label,line1=data.line1,line2=data.line2,
        city=data.city,state=data.state,pincode=data.pincode,phone=data.phone,
        latitude=data.latitude,longitude=data.longitude,is_default=make_default,
    )
    db.add(a);db.commit();db.refresh(a)
    return address_out(a)
@router.patch('/addresses/{address_id}')
def update_address(address_id:int,data:AddressUpdateInput,user:User=Depends(current_user),db:Session=Depends(get_db)):
    """Edit a saved address.

    Sending `latitude: null` clears the pin. Promotion to default demotes
    whichever address held it; demotion is ignored, because a user with any
    addresses must always have exactly one default.
    """
    a=db.get(Address,address_id)
    if not a or a.user_id!=user.id: raise HTTPException(404,'Address not found')

    payload=data.model_dump(exclude_unset=True)
    promote=payload.pop('is_default',None)

    for field,value in payload.items():
        setattr(a,field,value)

    if promote:
        for other in db.scalars(select(Address).where(Address.user_id==user.id,Address.id!=a.id)).all():
            other.is_default=False
        a.is_default=True

    db.commit();db.refresh(a)
    return address_out(a)
@router.delete('/addresses/{address_id}')
def delete_address(address_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    a=db.get(Address,address_id)
    if not a or a.user_id!=user.id: raise HTTPException(404,'Address not found')
    was_default=a.is_default
    db.delete(a);db.commit()
    if was_default:
        nxt=db.scalar(select(Address).where(Address.user_id==user.id).order_by(Address.created_at.asc()))
        if nxt is not None:
            nxt.is_default=True;db.commit()
    return {'ok':True}

# ---------------------------------------------------------------------------
# Saved payment methods
# ---------------------------------------------------------------------------
@router.get('/payment-methods')
def list_payment_methods(user:User=Depends(current_user),db:Session=Depends(get_db)):
    rows=db.scalars(select(PaymentMethod).where(PaymentMethod.user_id==user.id).order_by(PaymentMethod.is_default.desc(),PaymentMethod.created_at.desc())).all()
    return [payment_out(p) for p in rows]
@router.post('/payment-methods')
def create_payment_method(data:PaymentMethodInput,user:User=Depends(current_user),db:Session=Depends(get_db)):
    if data.method_type=='card' and not data.last4:
        raise HTTPException(422,'Card methods need the last 4 digits')
    if data.last4 and (not data.last4.isdigit() or len(data.last4)!=4):
        raise HTTPException(422,'Last 4 digits must be exactly four numbers')
    existing=db.scalar(select(func.count()).select_from(PaymentMethod).where(PaymentMethod.user_id==user.id)) or 0
    make_default=data.is_default or existing==0
    if make_default:
        for p in db.scalars(select(PaymentMethod).where(PaymentMethod.user_id==user.id)).all(): p.is_default=False
    p=PaymentMethod(user_id=user.id,label=data.label,method_type=data.method_type,last4=data.last4,is_default=make_default)
    db.add(p);db.commit();db.refresh(p)
    return payment_out(p)
@router.delete('/payment-methods/{method_id}')
def delete_payment_method(method_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    p=db.get(PaymentMethod,method_id)
    if not p or p.user_id!=user.id: raise HTTPException(404,'Payment method not found')
    was_default=p.is_default
    db.delete(p);db.commit()
    if was_default:
        nxt=db.scalar(select(PaymentMethod).where(PaymentMethod.user_id==user.id).order_by(PaymentMethod.created_at.asc()))
        if nxt is not None:
            nxt.is_default=True;db.commit()
    return {'ok':True}

# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------
def _validate_order_item(db:Session,user:User,listing_id:int)->Listing:
    """Everything about placing an order that is not about stock.

    The stock check used to live here as a Python `if`, which cannot be made
    safe: two requests that both read 10 available will both pass it. Reserving
    is now a guarded UPDATE in _reserve_stock, so this function only answers
    questions the database is not competing over.
    """
    x=db.get(Listing,listing_id)
    if not x or x.status!='active': raise HTTPException(422,'Listing is unavailable')
    if x.farmer_id==user.id: raise HTTPException(422,'You cannot order your own listing')
    if freshness(x)[0]=='Expired': raise HTTPException(422,'This listing has expired')
    cooldown=get_settings().buyer_rejection_cooldown_hours
    cutoff=datetime.utcnow()-timedelta(hours=cooldown)
    blocked=db.scalar(select(Order).where(Order.buyer_id==user.id,Order.listing_id==x.id,Order.status=='rejected',Order.status_changed_at>=cutoff))
    if blocked: raise HTTPException(429,f'The farmer declined a recent order from you on this listing. You can order it again {cooldown} hours after that decision.')
    return x
def _reserve_stock(db:Session,listing:Listing,quantity:float)->None:
    """Take `quantity` off a listing's available stock, atomically.

    A read-then-decrement cannot be made safe. Two requests that both read 10
    available will both decrement, and whichever commits second wins — the
    other order is confirmed against stock that no longer exists. This issues a
    single guarded UPDATE so the database decides the winner and the loser sees
    rowcount 0.

    Raises 422 when the guard does not match. On success the loaded listing is
    refreshed, so a caller reading `available_quantity` afterwards gets the new
    value rather than the one it was holding.
    """
    result=db.execute(
        update(Listing)
        .where(
            Listing.id==listing.id,
            Listing.status=='active',
            Listing.available_quantity>=quantity,
        )
        .values(available_quantity=Listing.available_quantity-quantity)
    )
    if result.rowcount==0:
        # The guard matched nothing. The loaded object still holds the value
        # from before the attempt, so expire it to re-read and say which
        # condition failed rather than reporting a bare conflict.
        db.expire(listing)
        if listing.status!='active':
            raise HTTPException(422,'Listing is unavailable')
        raise HTTPException(422,f'Only {listing.available_quantity} {listing.unit} left')
    db.refresh(listing)
def _delivery_fields(method:str,address:str|None,lat:float|None,lng:float|None)->dict:
    if method!='delivery':
        return {
            'delivery_method':'pickup',
            'delivery_address':None,
            'delivery_latitude':None,
            'delivery_longitude':None,
            'delivery_status':None,
        }
    return {
        'delivery_method':'delivery',
        'delivery_address':address,
        'delivery_latitude':lat,
        'delivery_longitude':lng,
        'delivery_status':'pending',
    }
def _require_delivery_pin(method:str,address:str|None,lat:float|None,lng:float|None)->None:
    """A delivery order must carry a pinned address.

    The address alone is not enough: a farmer's route is built from
    coordinates, so an order without them can only ever land in the unroutable
    bucket. Requiring the pin up front keeps that bucket for legacy rows and
    subscription cycles rather than making it the normal path.

    Pickup is unaffected — it has no destination to route to.
    """
    if method!='delivery':
        return
    if not address:
        raise HTTPException(422,'A delivery order needs a delivery address')
    if lat is None or lng is None:
        raise HTTPException(422,'A delivery order needs a pinned address. Choose one with a map pin, or switch to pickup.')
@router.post('/orders')
def create_order(data:OrderCreate,user:User=Depends(require_roles('buyer')),db:Session=Depends(get_db)):
    _require_delivery_pin(data.delivery_method,data.delivery_address,data.delivery_latitude,data.delivery_longitude)
    x=_validate_order_item(db,user,data.listing_id)
    _reserve_stock(db,x,data.quantity)
    now=datetime.utcnow()
    delivery=_delivery_fields(data.delivery_method,data.delivery_address,data.delivery_latitude,data.delivery_longitude)
    order=Order(
        buyer_id=user.id,farmer_id=x.farmer_id,listing_id=x.id,
        quantity=data.quantity,total_amount=data.quantity*x.price_per_unit,
        payment_mode=data.payment_mode,payment_label=data.payment_label,
        status='requested',status_changed_at=now,
        **delivery,
    )
    db.add(order);db.commit();db.refresh(order)
    return {'id':order.id,'status':order.status,'available_quantity':x.available_quantity}
@router.post('/orders/checkout')
def checkout(data:CheckoutInput,user:User=Depends(require_roles('buyer')),db:Session=Depends(get_db)):
    _require_delivery_pin(data.delivery_method,data.delivery_address,data.delivery_latitude,data.delivery_longitude)
    created=[]
    failed=[]
    for item in data.items:
        try:
            x=_validate_order_item(db,user,item.listing_id)
            _reserve_stock(db,x,item.quantity)
            now=datetime.utcnow()
            delivery=_delivery_fields(data.delivery_method,data.delivery_address,data.delivery_latitude,data.delivery_longitude)
            order=Order(
                buyer_id=user.id,farmer_id=x.farmer_id,listing_id=x.id,
                quantity=item.quantity,total_amount=item.quantity*x.price_per_unit,
                payment_mode=data.payment_mode,payment_label=data.payment_label,
                status='requested',status_changed_at=now,
                **delivery,
            )
            db.add(order)
            db.commit()
            db.refresh(order)
            created.append({'listing_id':x.id,'order_id':order.id,'title':x.title,'quantity':order.quantity,'total_amount':order.total_amount})
        except HTTPException as e:
            db.rollback()
            failed.append({'listing_id':item.listing_id,'reason':str(e.detail)})
    return {'created':created,'failed':failed,'delivery_address':data.delivery_address,'payment_label':data.payment_label,'delivery_method':data.delivery_method}
@router.get('/orders')
def orders(user:User=Depends(current_user),db:Session=Depends(get_db)):
    if user.role=='farmer':
        rows=db.execute(select(Order,Listing.title,User.name).join(Listing,Order.listing_id==Listing.id).join(User,Order.buyer_id==User.id).where(Order.farmer_id==user.id).order_by(Order.created_at.desc())).all()
    else:
        rows=db.execute(select(Order,Listing.title,User.name).join(Listing,Order.listing_id==Listing.id).join(User,Order.farmer_id==User.id).where(Order.buyer_id==user.id).order_by(Order.created_at.desc())).all()
    return [order_out(o,title,name) for o,title,name in rows]
@router.patch('/orders/{order_id}/status')
def update_order_status(order_id:int,data:OrderStatusInput,user:User=Depends(current_user),db:Session=Depends(get_db)):
    order=db.get(Order,order_id)
    if not order: raise HTTPException(404,'Order not found')

    is_farmer=user.role=='farmer' and order.farmer_id==user.id
    is_buyer=user.role=='buyer' and order.buyer_id==user.id
    is_admin=user.role=='admin'
    if not (is_farmer or is_buyer or is_admin): raise HTTPException(403,'This is not your order')

    target=data.status
    if target not in ALLOWED_TRANSITIONS.get(order.status,set()):
        raise HTTPException(409,f'Cannot move an order from {order.status} to {target}')
    if is_buyer and target!='cancelled': raise HTTPException(403,'Buyers can only cancel an order')
    if is_farmer and target not in {'accepted','rejected','completed'}: raise HTTPException(403,'Farmers cannot set that status')

    if target=='completed' and order.delivery_method=='delivery' and order.delivery_status!='delivered':
        raise HTTPException(409,'A delivery order can only be completed once its delivery has been marked delivered')

    if target in {'rejected','cancelled'}:
        listing=db.get(Listing,order.listing_id)
        if listing is not None: listing.available_quantity+=order.quantity

    order.status=target
    order.status_changed_at=datetime.utcnow()
    if target=='accepted' and order.delivery_method=='delivery' and order.delivery_status is None:
        order.delivery_status='pending'
    if target=='cancelled' and order.delivery_method=='delivery' and order.delivery_status not in CLOSED_DELIVERY_STATUSES:
        order.delivery_status='failed'
        order.delivery_note='Order cancelled before delivery completed'
    db.commit()
    return {'id':order.id,'status':order.status}
@router.post('/orders/{order_id}/reopen')
def reopen_order(order_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    order=db.get(Order,order_id)
    if not order: raise HTTPException(404,'Order not found')

    is_farmer=user.role=='farmer' and order.farmer_id==user.id
    is_admin=user.role=='admin'
    if not (is_farmer or is_admin): raise HTTPException(403,'Only the farmer or an admin can reopen an order')

    if order.status not in REOPENABLE_ORDER_STATUSES:
        raise HTTPException(409,f'{order.status} orders cannot be reopened')

    now=datetime.utcnow()
    available_at=order.status_changed_at+timedelta(days=REOPEN_WINDOW_DAYS)
    if now<available_at:
        remaining=available_at-now
        hours=max(1,math.ceil(remaining.total_seconds()/3600))
        window='day' if REOPEN_WINDOW_DAYS==1 else 'days'
        raise HTTPException(409,f'An order can be reopened {REOPEN_WINDOW_DAYS} {window} after it was {order.status}. Try again in about {hours} hour{"s" if hours!=1 else ""}.')

    listing=db.get(Listing,order.listing_id)
    if listing is None: raise HTTPException(404,'The listing for this order no longer exists')
    if listing.available_quantity<=0:
        raise HTTPException(409,'No stock is available, so this order cannot be reopened')

    original_quantity=order.quantity
    new_quantity=min(original_quantity,listing.available_quantity)
    try:
        _reserve_stock(db,listing,new_quantity)
    except HTTPException:
        # The read above and the reserve are not one operation. If stock moved
        # between them, refusing is the honest answer — quietly taking less
        # would confirm an order the farmer never agreed to.
        raise HTTPException(409,'No stock is available, so this order cannot be reopened')

    order.quantity=new_quantity
    order.total_amount=new_quantity*listing.price_per_unit
    order.status='requested'
    order.status_changed_at=datetime.utcnow()
    if order.delivery_method=='delivery':
        order.delivery_status=None
        order.delivery_note=None
    db.commit()
    return {'id':order.id,'status':order.status,'quantity':order.quantity,'total_amount':order.total_amount,'capped':new_quantity<original_quantity}
@router.get('/dashboard/summary')
def dashboard_summary(user:User=Depends(current_user),db:Session=Depends(get_db)):
    if user.role=='farmer':
        own=db.scalars(select(Listing).where(Listing.farmer_id==user.id)).all()
        active=sum(1 for x in own if x.status=='active' and freshness(x)[0]!='Expired')
        # Expired means "live stock that has run out of time". A removed or
        # suspended listing is already off the marketplace, so counting it here
        # would tell the farmer to act on something they cannot sell.
        expired=sum(1 for x in own if x.status=='active' and freshness(x)[0]=='Expired')
        open_orders=sum(1 for o in db.scalars(select(Order).where(Order.farmer_id==user.id)).all() if o.status not in TERMINAL_ORDER_STATUSES)
        deliveries=db.scalar(select(func.count()).select_from(Order).where(
            Order.farmer_id==user.id,
            Order.status=='accepted',
            Order.delivery_method=='delivery',
            Order.delivery_status.notin_(CLOSED_DELIVERY_STATUSES),
        )) or 0
        return {'active_listings':active,'open_orders':open_orders,'expired_listings':expired,'open_deliveries':deliveries}
    live=[x for x in db.scalars(select(Listing).where(Listing.status=='active')).all() if freshness(x)[0]!='Expired']
    open_orders=sum(1 for o in db.scalars(select(Order).where(Order.buyer_id==user.id)).all() if o.status not in TERMINAL_ORDER_STATUSES)
    return {'available_now':len(live),'open_orders':open_orders,'categories':len({x.category_id for x in live})}

# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------
@router.get('/recommendations/listings')
def recommendations(user:User=Depends(current_user),db:Session=Depends(get_db)):
    """Listings this buyer is most likely to want, each carrying why.

    Ranked by what the buyer has actually bought rather than by recency. This
    used to sort everything by remaining freshness, which made "Recommended for
    You" mean "the newest four listings" and nothing more.

    A buyer with no order history — which is every farmer, since ordering is
    buyer-only — falls back to freshest-first, so the old behaviour is still the
    floor rather than something that was thrown away.

    Two signals, in order: the category the buyer keeps coming back to, then the
    farmer they keep buying from. Freshness breaks ties inside each tier and is
    capped, so a long shelf life cannot outrank real history.
    """
    rows=db.scalars(
        select(Listing)
        .options(joinedload(Listing.farmer),joinedload(Listing.category))
        .where(Listing.status=='active')
    ).unique().all()

    # One query for the whole history rather than one per candidate listing.
    # Cancelled orders are excluded: the buyer withdrew, so it is not evidence
    # of what they want.
    category_counts={}
    farmer_counts={}
    for category_id,farmer_id,count in db.execute(
        select(Listing.category_id,Order.farmer_id,func.count())
        .join(Listing,Order.listing_id==Listing.id)
        .where(Order.buyer_id==user.id,Order.status!='cancelled')
        .group_by(Listing.category_id,Order.farmer_id)
    ).all():
        category_counts[category_id]=category_counts.get(category_id,0)+count
        farmer_counts[farmer_id]=farmer_counts.get(farmer_id,0)+count

    scored=[]
    for x in rows:
        status,hours=freshness(x)
        if status=='Expired':
            continue
        category_hits=category_counts.get(x.category_id,0)
        farmer_hits=farmer_counts.get(x.farmer_id,0)
        score=min(category_hits*CATEGORY_AFFINITY_PER_ORDER,CATEGORY_AFFINITY_CAP)
        if farmer_hits:
            score+=FARMER_AFFINITY_BONUS
        score+=min(hours,FRESHNESS_SCORE_CAP_HOURS)/48.0
        scored.append((x,status,hours,score,category_hits,farmer_hits))

    scored.sort(key=lambda t:t[3],reverse=True)

    out=[]
    for x,status,hours,score,category_hits,farmer_hits in scored[:RECOMMENDATION_LIMIT]:
        # The reason names the strongest signal behind this particular pick, so
        # it is true for the listing it is attached to rather than a generic
        # line repeated on every card.
        if category_hits:
            times='time' if category_hits==1 else 'times'
            reason=f'You have ordered {x.category.name} {category_hits} {times} before'
        elif farmer_hits:
            reason=f'You have ordered from {x.farmer.name} before'
        else:
            reason='Fresh today'
        out.append(listing_out(x,status,hours,reason=reason))
    return out
