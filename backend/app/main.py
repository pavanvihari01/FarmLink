from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.core.config import get_settings
from app.db.seed import seed
from app.db.session import Base, SessionLocal, engine
from app.models import entities

app=FastAPI(title='FarmLink API',version='0.1.0')
app.add_middleware(CORSMiddleware,allow_origins=[get_settings().frontend_origin],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
@app.on_event('startup')
def startup():
    Base.metadata.create_all(bind=engine)
    db=SessionLocal(); seed(db); db.close()
app.include_router(router)
@app.get('/health')
def health(): return {'status':'ok','service':'farmlink-api'}
