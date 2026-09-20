from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import UPLOAD_DIR, get_settings
from app.db.seed import seed
from app.db.session import Base, SessionLocal, engine
from app.models import entities  # noqa: F401  (registers models on Base.metadata)

settings = get_settings()

app = FastAPI(title='FarmLink API', version='0.1.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

@app.on_event('startup')
def startup() -> None:
    # SQLite keeps the zero-config dev experience: create tables on boot.
    # PostgreSQL is migration-driven; run `alembic upgrade head` before starting.
    if settings.database_url.startswith('sqlite'):
        Base.metadata.create_all(bind=engine)

    if settings.demo_mode:
        db = SessionLocal()
        try:
            seed(db)
        finally:
            db.close()

app.include_router(router)

# Uploaded listing photos. StaticFiles validates that the directory exists when
# the app is constructed, so it is created here rather than in startup().
# Mounted after include_router so a future /uploads/... API route would win.
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount('/uploads', StaticFiles(directory=UPLOAD_DIR), name='uploads')

@app.get('/health')
def health() -> dict:
    return {'status': 'ok', 'service': 'farmlink-api'}
