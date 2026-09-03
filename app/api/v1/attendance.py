"""
Attendance Management API Router
Handles live check-in with camera selfie capture, geolocation, IP logging, and instant on-demand certificate assignment.
"""

import io
import os
import uuid
import base64
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.database import get_db
from app.models import Event, Paper, Attendance, User, Participant, Certificate
from app.schemas.attendance import AttendanceCreate, AttendanceResponse, AttendanceCheckInResult
from app.api.deps import get_current_user
from app.services import minio_service, generate_claim_code
from app.config import settings

router = APIRouter(tags=["Attendance Management"])


def extract_client_ip(request: Request) -> str:
    """Extracts client IP address handling reverse proxies and load balancers"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    if request.client:
        return request.client.host
    return "127.0.0.1"


@router.get("/events/{event_id}/attendance/public-info")
def get_public_attendance_info(event_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Public endpoint providing event metadata and paper catalog for attendance form autocomplete.
    """
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")

    papers = db.query(Paper).filter(Paper.event_id == event_id).order_by(Paper.paper_code.asc()).all()

    return {
        "event_id": event.id,
        "event_name": event.name,
        "event_type": event.event_type,
        "location": event.location,
        "event_date": event.event_date.strftime("%A, %d %B %Y"),
        "description": event.description or "",
        "status": event.status,
        "papers": [
            {
                "id": str(p.id),
                "paper_code": p.paper_code or "",
                "title": p.title,
                "authors": p.authors or "",
                "presenter_name": p.presenter_name or ""
            }
            for p in papers
        ]
    }


@router.post("/events/{event_id}/attendance/check-in", response_model=AttendanceCheckInResult, status_code=status.HTTP_201_CREATED)
def submit_attendance_check_in(
    event_id: uuid.UUID,
    check_in: AttendanceCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Public check-in endpoint:
    1. Validates live selfie photo & uploads to MinIO.
    2. Logs Geolocation GPS & Client IP.
    3. Generates an instant Certificate Claim Code (ready for On-Demand download).
    """
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found.")

    # 1. Process base64 live photo
    photo_str = check_in.photo_base64
    if "," in photo_str:
        photo_str = photo_str.split(",")[1]
    
    try:
        photo_bytes = base64.b64decode(photo_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Format foto tidak valid. Wajib ambil foto dari kamera live.")

    if len(photo_bytes) < 1000:
        raise HTTPException(status_code=400, detail="Foto terlalu kecil atau kosong. Ambil foto kamera live yang jelas.")

    photo_filename = f"attendances/{event_id}/{uuid.uuid4()}.jpg"
    photo_url = minio_service.upload_bytes(
        bucket_name=settings.MINIO_BUCKET_CERTIFICATES,
        object_name=photo_filename,
        data=photo_bytes,
        content_type="image/jpeg"
    )

    # 2. Extract client IP & User Agent
    client_ip = extract_client_ip(request)
    user_agent = request.headers.get("user-agent", "Unknown Device")

    # 3. Resolve Paper Title & Code if paper_id or paper_code provided (for Presenter / Author)
    final_paper_title = check_in.paper_title
    paper_obj = None
    if check_in.paper_id:
        paper_obj = db.query(Paper).filter(Paper.id == check_in.paper_id, Paper.event_id == event_id).first()
    elif check_in.paper_code and check_in.paper_code.strip():
        code_clean = check_in.paper_code.strip()
        paper_obj = db.query(Paper).filter(
            Paper.event_id == event_id,
            func.lower(Paper.paper_code) == code_clean.lower()
        ).first()

    if paper_obj:
        final_paper_title = paper_obj.title
        check_in.paper_id = paper_obj.id

    # Strict validation: Author MUST have a valid registered paper in the event catalog
    if check_in.role == "Author":
        if not paper_obj:
            raise HTTPException(
                status_code=400,
                detail="Paper ID / Kode Paper tidak ditemukan di Katalog Judul Paper acara ini. Pastikan Paper ID Anda sudah terdaftar."
            )

    # 4. Save Attendance Record
    attendance = Attendance(
        event_id=event_id,
        paper_id=check_in.paper_id,
        full_name=check_in.full_name.strip(),
        email=check_in.email.strip() if check_in.email else None,
        phone_number=check_in.phone_number.strip() if check_in.phone_number else None,
        institution=check_in.institution.strip(),
        role=check_in.role.strip() if check_in.role else "Participant",
        paper_title=final_paper_title.strip() if final_paper_title else None,
        photo_url=photo_url,
        latitude=check_in.latitude,
        longitude=check_in.longitude,
        accuracy_meters=check_in.accuracy_meters,
        ip_address=client_ip,
        user_agent=user_agent,
        created_at=datetime.now(timezone.utc)
    )
    db.add(attendance)
    db.flush()

    # 5. Create Participant and Assign On-Demand Certificate
    # Generate unique 8-character claim code
    claim_code = generate_claim_code()
    while db.query(Certificate).filter(Certificate.claim_code == claim_code).first():
        claim_code = generate_claim_code()

    if event.cert_prefix and event.cert_prefix.strip():
        prefix = event.cert_prefix.strip().upper()
        cert_num = f"{prefix}-{claim_code}"
    else:
        default_prefix = event.name[:4].upper().replace(" ", "C")
        cert_num = f"{default_prefix}-{datetime.now().year}-{claim_code}"

    participant = Participant(
        event_id=event_id,
        name=attendance.full_name,
        email=attendance.email if attendance.email else f"attendee_{attendance.id.hex[:6]}@uinjkt.ac.id",
        role=attendance.role,
        paper_title=attendance.paper_title,
        custom_data={
            "institution": attendance.institution,
            "phone_number": attendance.phone_number or "",
            "attendance_id": str(attendance.id),
            "paper_code": paper_obj.paper_code if paper_obj else (check_in.paper_code or ""),
            "paper_id": str(paper_obj.id) if paper_obj else ""
        }
    )
    db.add(participant)
    db.flush()

    certificate = Certificate(
        event_id=event_id,
        participant_id=participant.id,
        certificate_number=cert_num,
        claim_code=claim_code,
        status="GENERATED",
        download_count=0
    )
    db.add(certificate)
    db.commit()

    return {
        "success": True,
        "check_in_id": attendance.id,
        "full_name": attendance.full_name,
        "event_name": event.name,
        "role": attendance.role,
        "claim_code": claim_code,
        "cert_url": f"/verify/{claim_code}",
        "timestamp": attendance.created_at,
        "message": f"Thank you, {attendance.full_name}! Your check-in is verified. Your Certificate Claim Code is {claim_code}."
    }


@router.get("/events/{event_id}/attendance", response_model=List[AttendanceResponse])
def list_event_attendances(
    event_id: uuid.UUID,
    role: Optional[str] = Query(None, description="Filter by role"),
    q: Optional[str] = Query(None, description="Search name, email, phone, institution, or paper title"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Organizer endpoint to list all attendance records for an event with claim code links.
    """
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == current_user.id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Acara tidak ditemukan.")

    query = db.query(Attendance).filter(Attendance.event_id == event_id)
    if role:
        query = query.filter(Attendance.role.ilike(role.strip()))
    if q:
        search_pattern = f"%{q.strip()}%"
        query = query.filter(
            (Attendance.full_name.ilike(search_pattern)) |
            (Attendance.email.ilike(search_pattern)) |
            (Attendance.phone_number.ilike(search_pattern)) |
            (Attendance.institution.ilike(search_pattern)) |
            (Attendance.paper_title.ilike(search_pattern)) |
            (Attendance.ip_address.ilike(search_pattern))
        )

    attendances = query.order_by(desc(Attendance.created_at)).all()

    # Match each attendance with certificate claim code
    results = []
    for att in attendances:
        p = db.query(Participant).filter(
            Participant.event_id == event_id,
            Participant.name == att.full_name,
            Participant.role == att.role
        ).order_by(Participant.created_at.desc()).first()

        code = None
        if p and p.certificate:
            code = p.certificate.claim_code

        paper_code_val = att.paper.paper_code if att.paper else (
            p.custom_data.get("paper_code") if (p and p.custom_data and isinstance(p.custom_data, dict)) else None
        )

        results.append({
            "id": att.id,
            "event_id": att.event_id,
            "paper_id": att.paper_id,
            "paper_code": paper_code_val,
            "full_name": att.full_name,
            "email": att.email,
            "phone_number": att.phone_number,
            "institution": att.institution,
            "role": att.role,
            "paper_title": att.paper_title,
            "photo_url": att.photo_url,
            "latitude": att.latitude,
            "longitude": att.longitude,
            "accuracy_meters": att.accuracy_meters,
            "ip_address": att.ip_address,
            "user_agent": att.user_agent,
            "created_at": att.created_at,
            "claim_code": code
        })

    return results
