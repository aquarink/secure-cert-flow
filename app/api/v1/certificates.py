"""
Certificate Management Endpoints for Organizers
"""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Event, Certificate, User
from app.schemas.certificate import CertificateResponse
from app.api.deps import get_current_user

router = APIRouter(tags=["Certificates"])


@router.get("/events/{event_id}/certificates")
def list_event_certificates(
    event_id: uuid.UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lists certificates generated for an event with pagination and search filter"""
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == current_user.id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Acara tidak ditemukan.")

    query = db.query(Certificate).filter(Certificate.event_id == event_id)
    if status:
        query = query.filter(Certificate.status == status.upper())

    total = query.count()
    certs = query.order_by(Certificate.created_at.desc()).offset((page - 1) * limit).limit(limit).all()

    result = []
    for c in certs:
        p = c.participant
        result.append({
            "id": c.id,
            "event_id": c.event_id,
            "participant_id": c.participant_id,
            "participant_name": p.name if p else "",
            "participant_email": p.email if p else "",
            "participant_role": p.role if p else "",
            "paper_title": p.paper_title if p else "",
            "certificate_number": c.certificate_number,
            "claim_code": c.claim_code,
            "status": c.status,
            "image_url": c.image_url,
            "checksum_sha256": c.checksum_sha256,
            "download_count": c.download_count,
            "claimed_at": c.claimed_at,
            "error_message": c.error_message,
            "created_at": c.created_at,
        })

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "data": result
    }


@router.get("/certificates/{cert_id}", response_model=CertificateResponse)
def get_certificate_detail(
    cert_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Gets detailed info for a single certificate record"""
    cert = db.query(Certificate).filter(Certificate.id == cert_id).first()
    if not cert:
        raise HTTPException(status_code=404, detail="Sertifikat tidak ditemukan.")

    # Validate organizer ownership
    if cert.event.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Akses ditolak.")

    return cert
