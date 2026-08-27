"""
API Version 1 Router Aggregator
"""

from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.events import router as events_router
from app.api.v1.templates import router as templates_router
from app.api.v1.bulk import router as bulk_router
from app.api.v1.certificates import router as certs_router
from app.api.v1.claim import router as claim_router
from app.api.v1.webhooks import router as webhooks_router

api_v1_router = APIRouter(prefix="/v1")

api_v1_router.include_router(auth_router)
api_v1_router.include_router(events_router)
api_v1_router.include_router(templates_router)
api_v1_router.include_router(bulk_router)
api_v1_router.include_router(certs_router)
api_v1_router.include_router(claim_router)
api_v1_router.include_router(webhooks_router)
