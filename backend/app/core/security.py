from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.db.session import get_db
from app.models.entities import User

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/auth/login')
def hash_password(value:str): return pwd_context.hash(value)
def verify_password(value:str, hashed:str): return pwd_context.verify(value, hashed)
def make_token(user:User): return jwt.encode({'sub':str(user.id),'role':user.role,'exp':datetime.utcnow()+timedelta(minutes=get_settings().jwt_expire_minutes)},get_settings().jwt_secret,algorithm='HS256')
def current_user(token:str=Depends(oauth2_scheme), db:Session=Depends(get_db)):
    try: user_id=int(jwt.decode(token,get_settings().jwt_secret,algorithms=['HS256'])['sub'])
    except (JWTError, KeyError, ValueError): raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid or expired session')
    user=db.get(User,user_id)
    if not user or not user.is_active: raise HTTPException(status_code=401,detail='Inactive account')
    return user
def require_roles(*roles):
    def checker(user:User=Depends(current_user)):
        if user.role not in roles: raise HTTPException(status_code=403,detail='This action is not available for your role')
        return user
    return checker
