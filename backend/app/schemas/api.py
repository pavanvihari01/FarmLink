from datetime import datetime
from typing import Literal
from pydantic import BaseModel, EmailStr, Field

class RegisterInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8)
    role: str = 'buyer'
    phone: str | None = None
class LoginInput(BaseModel): email: EmailStr; password: str

class UserOut(BaseModel):
    id:int
    name:str
    email:EmailStr
    role:str
    is_active:bool=True
    phone:str|None=None

class AuthOut(BaseModel): access_token:str; token_type:str='bearer'; user:UserOut

# Every field optional. None means "leave this alone"; an empty string for phone
# means "clear it".
class ProfileUpdateInput(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)

class PasswordChangeInput(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=200)

class FarmerOut(BaseModel):
    id: int
    name: str
    location: str | None = None

class ListingCreate(BaseModel):
    category_id:int
    title:str
    description:str=''
    price_per_unit:float=Field(gt=0)
    unit:str='kg'
    available_quantity:float=Field(gt=0)
    harvest_time:datetime|None=None
    lifespan_hours:int=Field(gt=0,le=720)
    organic:bool=False
    bulk_available:bool=False
    location_text:str
    latitude:float|None=None
    longitude:float|None=None
    image_url:str='/images/market-harvest.png'

# Every field optional. Only what the caller sends is applied — pydantic's
# exclude_unset is what makes "did not mention it" different from "set it to
# null". `status` is deliberately absent: removing a listing goes through
# DELETE so the open-order guard cannot be bypassed.
class ListingUpdate(BaseModel):
    category_id: int | None = None
    title: str | None = Field(default=None, min_length=1, max_length=140)
    description: str | None = None
    price_per_unit: float | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, min_length=1, max_length=20)
    available_quantity: float | None = Field(default=None, ge=0)
    harvest_time: datetime | None = None
    lifespan_hours: int | None = Field(default=None, gt=0, le=720)
    organic: bool | None = None
    bulk_available: bool | None = None
    location_text: str | None = Field(default=None, min_length=1, max_length=140)
    latitude: float | None = None
    longitude: float | None = None
    image_url: str | None = None

class OrderCreate(BaseModel):
    listing_id:int
    quantity:float=Field(gt=0)
    payment_mode:str='demo'
    delivery_address:str|None=None
    payment_label:str|None=None
    delivery_method:Literal['pickup','delivery']='pickup'
    delivery_latitude:float|None=None
    delivery_longitude:float|None=None

class OrderStatusInput(BaseModel):
    status: Literal['accepted', 'rejected', 'completed', 'cancelled']

class DeliveryStatusInput(BaseModel):
    status: Literal['pending', 'out_for_delivery', 'delivered', 'failed']
    note: str | None = Field(default=None, max_length=500)

class AddressInput(BaseModel):
    label: str = Field(min_length=1, max_length=60)
    line1: str = Field(min_length=1, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=1, max_length=100)
    pincode: str = Field(min_length=1, max_length=12)
    phone: str | None = Field(default=None, max_length=30)
    latitude: float | None = None
    longitude: float | None = None
    is_default: bool = False

# Same shape, every field optional. Sending latitude: null clears the pin.
class AddressUpdateInput(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=60)
    line1: str | None = Field(default=None, min_length=1, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, min_length=1, max_length=100)
    state: str | None = Field(default=None, min_length=1, max_length=100)
    pincode: str | None = Field(default=None, min_length=1, max_length=12)
    phone: str | None = Field(default=None, max_length=30)
    latitude: float | None = None
    longitude: float | None = None
    # Setting this true demotes whichever address was the default. Setting it
    # false is ignored — a user must always have one default once they have any.
    is_default: bool | None = None

class PaymentMethodInput(BaseModel):
    label: str = Field(min_length=1, max_length=60)
    method_type: Literal['upi', 'card', 'cod']
    last4: str | None = Field(default=None, max_length=4)
    is_default: bool = False

class CheckoutItem(BaseModel):
    listing_id: int
    quantity: float = Field(gt=0)

class CheckoutInput(BaseModel):
    items: list[CheckoutItem] = Field(min_length=1)
    delivery_address: str | None = None
    payment_mode: str = 'demo'
    payment_label: str | None = None
    delivery_method: Literal['pickup', 'delivery'] = 'pickup'
    delivery_latitude: float | None = None
    delivery_longitude: float | None = None

class ReportInput(BaseModel):
    listing_id: int
    reason: Literal['fake_lifespan', 'wrong_quantity', 'bad_quality', 'no_show', 'other']
    details: str | None = Field(default=None, max_length=2000)

class ReportResolveInput(BaseModel):
    status: Literal['resolved', 'dismissed']
    note: str | None = Field(default=None, max_length=1000)

class SubscriptionInput(BaseModel):
    farmer_id: int
    category_id: int
    quantity: float = Field(gt=0)
    unit: str = Field(default='kg', min_length=1, max_length=20)
    frequency_days: Literal[7, 14, 30]
    delivery_address: str = Field(min_length=1)
    # Optional, mirroring the address form. Without a pin the generated order
    # is still a delivery; it just cannot be placed on the route map.
    delivery_latitude: float | None = None
    delivery_longitude: float | None = None
    payment_label: str | None = Field(default=None, max_length=120)

# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------
class UserActiveInput(BaseModel):
    is_active: bool

class AdminListingStatusInput(BaseModel):
    status: Literal['active', 'suspended', 'removed']
    moderation_note: str | None = Field(default=None, max_length=1000)
    cancel_open_orders: bool = False

class CategoryInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    default_lifespan_hours: int = Field(gt=0, le=720)

class CategoryUpdateInput(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    default_lifespan_hours: int | None = Field(default=None, gt=0, le=720)
