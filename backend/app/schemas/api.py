from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

class RegisterInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8)
    role: str = 'buyer'
    phone: str | None = None
class LoginInput(BaseModel): email: EmailStr; password: str
class UserOut(BaseModel): id:int; name:str; email:EmailStr; role:str
class AuthOut(BaseModel): access_token:str; token_type:str='bearer'; user:UserOut
class ListingCreate(BaseModel):
    category_id:int; title:str; description:str=''; price_per_unit:float=Field(gt=0); unit:str='kg'; available_quantity:float=Field(gt=0); harvest_time:datetime|None=None; lifespan_hours:int=Field(gt=0,le=720); organic:bool=False; bulk_available:bool=False; location_text:str; image_url:str='/images/market-harvest.png'
class OrderCreate(BaseModel): listing_id:int; quantity:float=Field(gt=0); payment_mode:str='demo'
