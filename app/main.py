"""
Secure Cert Flow - Automated Certificate Generator & Attendance Management System
Main Application Entry Point (FastAPI)
"""

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.database import engine, Base
from app.api import api_v1_router
from app.services import minio_service

# Configure standard structured logging
logging.basicConfig(
    level=logging.INFO if not settings.APP_DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("secure_cert_flow")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle event handler for application startup and shutdown"""
    logger.info("Initializing Secure Cert Flow application...")
    
    # 1. Ensure MinIO buckets are checked (non-blocking)
    try:
        minio_service.ensure_buckets()
    except Exception as e:
        logger.warning(f"MinIO initialization warning: {e}")

    # 2. Ensure Database schema is synced
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema synchronized successfully.")
    except Exception as e:
        logger.error(f"Database schema sync error: {e}")

    yield

    logger.info("Shutting down Secure Cert Flow application...")


app = FastAPI(
    title=settings.APP_NAME,
    description="Automated Certificate Generator & Attendance Management System",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Assets & Templates
STATIC_DIR = "/var/www/sertifikat/static"
TEMPLATES_DIR = "/var/www/sertifikat/templates"
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Mount API Routers
app.include_router(api_v1_router, prefix="/api")


@app.get("/favicon.ico", include_in_schema=False)
@app.get("/favicon.png", include_in_schema=False)
def favicon():
    """Serves application favicon"""
    favicon_path = os.path.join(STATIC_DIR, "images", "favicon.png")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path, media_type="image/png")
    return HTMLResponse(status_code=404)


@app.get("/health", tags=["System"])
def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "database": f"{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}",
        "minio": settings.MINIO_ENDPOINT,
        "kafka": settings.KAFKA_BOOTSTRAP_SERVERS,
    }


# Serve Integrated TailAdmin & Web UI Pages
@app.get("/", response_class=HTMLResponse, tags=["Web UI"])
def index_page(request: Request):
    """Home / Landing page"""
    if os.path.exists(os.path.join(TEMPLATES_DIR, "index.html")):
        return templates.TemplateResponse(request=request, name="index.html", context={"app_name": settings.APP_NAME})
    return HTMLResponse("<h2>Secure Cert Flow API Active</h2>")


@app.get("/login", response_class=HTMLResponse, tags=["Web UI"])
def login_page(request: Request):
    """Sign-in page styled with TailAdmin"""
    return templates.TemplateResponse(request=request, name="signin.html", context={"app_name": settings.APP_NAME})


@app.get("/register", response_class=HTMLResponse, tags=["Web UI"])
def register_page(request: Request):
    """Sign-up page styled with TailAdmin"""
    return templates.TemplateResponse(request=request, name="signup.html", context={"app_name": settings.APP_NAME})


@app.get("/dashboard", response_class=HTMLResponse, tags=["Web UI"])
def dashboard_page(request: Request):
    """Main organizer dashboard styled with TailAdmin"""
    return templates.TemplateResponse(request=request, name="dashboard.html", context={"app_name": settings.APP_NAME})


@app.get("/claim", response_class=HTMLResponse, tags=["Web UI"])
def claim_page(request: Request):
    """Public participant claim page"""
    return templates.TemplateResponse(request=request, name="claim.html", context={"app_name": settings.APP_NAME})


@app.get("/verify/{claim_code}", response_class=HTMLResponse, tags=["Web UI"])
def verify_page(request: Request, claim_code: str):
    """Public certificate validation page (QR scan target)"""
    return templates.TemplateResponse(request=request, name="verify.html", context={"claim_code": claim_code, "app_name": settings.APP_NAME})


@app.get("/attendance/{event_id}", response_class=HTMLResponse, tags=["Web UI"])
def attendance_page(request: Request, event_id: str):
    """Public participant attendance check-in page with live photo & GPS"""
    return templates.TemplateResponse(request=request, name="attendance.html", context={"event_id": event_id, "app_name": settings.APP_NAME})

from fastapi import HTTPException, Response

@app.get("/cert-outputs/{path:path}", tags=["Media"])
@app.get("/cert-templates/{path:path}", tags=["Media"])
@app.get("/cert-signatures/{path:path}", tags=["Media"])
@app.get("/api/v1/storage/{path:path}", tags=["Media"])
def serve_storage_media(path: str, request: Request):
    """
    Directly streams uploaded images (attendance selfies, certificates, templates) from MinIO/Storage
    """
    # Detect bucket from URL path or prefix
    raw_path = request.url.path
    if raw_path.startswith("/cert-outputs/"):
        bucket = settings.MINIO_BUCKET_CERTIFICATES
        obj_name = path
    elif raw_path.startswith("/cert-templates/"):
        bucket = settings.MINIO_BUCKET_TEMPLATES
        obj_name = path
    elif raw_path.startswith("/cert-signatures/"):
        bucket = settings.MINIO_BUCKET_SIGNATURES
        obj_name = path
    else:
        # /api/v1/storage/bucket/object_name or /api/v1/storage/object_name
        parts = path.split("/", 1)
        if len(parts) == 2 and parts[0] in ["cert-outputs", "cert-templates", "cert-signatures"]:
            bucket, obj_name = parts[0], parts[1]
        else:
            bucket = settings.MINIO_BUCKET_CERTIFICATES
            obj_name = path

    try:
        data = minio_service.download_bytes(bucket, obj_name)
        media_type = "image/jpeg" if obj_name.endswith(".jpg") or obj_name.endswith(".jpeg") else "image/png"
        return Response(content=data, media_type=media_type)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Media file not found: {str(e)}")
