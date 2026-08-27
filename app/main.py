"""
Secure Cert Flow - Automated Certificate Generator
Main Application Entry Point (FastAPI)
"""

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
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
    
    # 1. Ensure MinIO buckets are created
    try:
        minio_service.ensure_buckets()
        logger.info("MinIO bucket initialization completed.")
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
    description="Automated Certificate Generator & Fraud-Proof Verification System",
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


@app.get("/health", tags=["System"])
def health_check():
    """Health check endpoint for Docker / Kubernetes / load balancers"""
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "database": f"{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}",
        "minio": settings.MINIO_ENDPOINT,
        "kafka": settings.KAFKA_BOOTSTRAP_SERVERS,
    }


# Serve Integrated TailAdmin Pages
@app.get("/", response_class=HTMLResponse, tags=["Web UI"])
def index_page(request: Request):
    """Home / Landing page redirecting to dashboard or claim page"""
    if os.path.exists(os.path.join(TEMPLATES_DIR, "index.html")):
        return templates.TemplateResponse("index.html", {"request": request, "app_name": settings.APP_NAME})
    return HTMLResponse("<h2>Secure Cert Flow - Automated Certificate Generator API Active</h2><p>Visit <a href='/docs'>/docs</a> for API documentation.</p>")


@app.get("/login", response_class=HTMLResponse, tags=["Web UI"])
def login_page(request: Request):
    """Sign-in page styled with TailAdmin"""
    return templates.TemplateResponse("signin.html", {"request": request, "app_name": settings.APP_NAME})


@app.get("/register", response_class=HTMLResponse, tags=["Web UI"])
def register_page(request: Request):
    """Sign-up page styled with TailAdmin"""
    return templates.TemplateResponse("signup.html", {"request": request, "app_name": settings.APP_NAME})


@app.get("/dashboard", response_class=HTMLResponse, tags=["Web UI"])
def dashboard_page(request: Request):
    """Main organizer dashboard styled with TailAdmin"""
    return templates.TemplateResponse("dashboard.html", {"request": request, "app_name": settings.APP_NAME})


@app.get("/claim", response_class=HTMLResponse, tags=["Web UI"])
def claim_page(request: Request):
    """Public participant claim page"""
    return templates.TemplateResponse("claim.html", {"request": request, "app_name": settings.APP_NAME})


@app.get("/verify/{claim_code}", response_class=HTMLResponse, tags=["Web UI"])
def verify_page(request: Request, claim_code: str):
    """Public certificate validation page (QR scan target)"""
    return templates.TemplateResponse("verify.html", {"request": request, "claim_code": claim_code, "app_name": settings.APP_NAME})
