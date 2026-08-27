"""
Attendance Management API Router
Handles live check-in with camera selfie capture, geolocation, IP logging, and organizer reporting.
"""

import io
import os
import uuid
import base64
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models import Event, Paper, Attendance, User, Participant, Certificate, Batch
from app.schemas.attendance import AttendanceCreate, AttendanceResponse, AttendanceCheckInResult
from app.api.deps import get_current_user
from app.services import minio_service, kafka_service, generate_claim_code
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
    Public check-in endpoint for conference participants.
    Decodes live camera photo, logs GPS & IP address, and stores record.
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
        raise HTTPException(status_code=400, detail="Invalid photo format. Live camera capture required.")

    if len(photo_bytes) < 1000:
        raise HTTPException(status_code=400, detail="Photo is too small or blank. Please capture a clear live photo.")

    # Upload live selfie photo to object storage
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

    # 3. Resolve Paper Title if paper_id provided
    final_paper_title = check_in.paper_title
    if check_in.paper_id:
        paper_obj = db.query(Paper).filter(Paper.id == check_in.paper_id, Paper.event_id == event_id).first()
        if paper_obj:
            final_paper_title = paper_obj.title

    # 4. Save Attendance Record
    attendance = Attendance(
        event_id=event_id,
        paper_id=check_in.paper_id,
        full_name=check_in.full_name.strip(),
        institution=check_in.institution.strip(),
        role=check_in.role.strip(),
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
    db.commit()
    db.refresh(attendance)

    return {
        "success": True,
        "check_in_id": attendance.id,
        "full_name": attendance.full_name,
        "event_name": event.name,
        "role": attendance.role,
        "timestamp": attendance.created_at,
        "message": f"Thank you, {attendance.full_name}! Your attendance check-in has been successfully recorded."
    }


@router.get("/events/{event_id}/attendance", response_model=List[AttendanceResponse])
def list_event_attendances(
    event_id: uuid.UUID,
    role: Optional[str] = Query(None, description="Filter by role"),
    q: Optional[str] = Query(None, description="Search name, institution, or paper title"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Organizer endpoint to list all attendance records for an event.
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
            (Attendance.institution.ilike(search_pattern)) |
            (Attendance.paper_title.ilike(search_pattern)) |
            (Attendance.ip_address.ilike(search_pattern))
        )

    return query.order_by(desc(Attendance.created_at)).all()


@router.get("/events/{event_id}/attendance/export")
def export_attendance_csv(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Exports event attendance records as a clean CSV spreadsheet"""
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == current_user.id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Acara tidak ditemukan.")

    attendances = db.query(Attendance).filter(Attendance.event_id == event_id).order_by(Attendance.created_at.asc()).all()

    import csv
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Check-in ID", "Full Name", "Institution", "Role", "Paper Title", "Latitude", "Longitude", "IP Address", "Timestamp"])

    for a in attendances:
        writer.writerow([
            str(a.id),
            a.full_name,
            a.institution,
            a.role,
            a.paper_title or "-",
            a.latitude or "-",
            a.longitude or "-",
            a.ip_address or "-",
            a.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        ])

    csv_data = output.getvalue()
    filename = f"attendance_{event.name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv"
    
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post("/events/{event_id}/attendance/generate-certificates")
def generate_certificates_from_attendance(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Creates participant records and certificate generation jobs in Kafka
    directly from all verified attendees who checked in for this event.
    """
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == current_user.id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Acara tidak ditemukan.")

    attendances = db.query(Attendance).filter(Attendance.event_id == event_id).all()
    if not attendances:
        raise HTTPException(status_code=400, detail="Belum ada data presensi yang tercatat untuk acara ini.")

    # Create Batch
    batch = Batch(
        event_id=event_id,
        filename=f"Attendance-CheckIn-{datetime.now().strftime('%Y%m%d%H%M')}",
        total_records=len(attendances),
        processed_records=0,
        success_records=0,
        failed_records=0,
        status="processing"
    )
    db.add(batch)
    db.flush()

    dispatched = 0
    for a in attendances:
        # Create participant entry
        p = Participant(
            event_id=event_id,
            batch_id=batch.id,
            email=f"{a.full_name.lower().replace(' ', '')}@participant.local",
            name=a.full_name,
            role=a.role,
            paper_title=a.paper_title,
            custom_data={"institution": a.institution, "attendance_id": str(a.id)}
        )
        db.add(p)
        db.flush()

        # Create certificate record
        claim_code = generate_claim_code()
        cert_num = f"CERT-{datetime.now().strftime('%Y%m%d')}-{claim_code}"
        cert = Certificate(
            event_id=event_id,
            participant_id=p.id,
            batch_id=batch.id,
            certificate_number=cert_num,
            claim_code=claim_code,
            status="QUEUED"
        )
        db.add(cert)
        db.flush()

        # Dispatch job to Kafka
        kafka_payload = {
            "certificate_id": str(cert.id),
            "event_id": str(event_id),
            "participant_id": str(p.id),
            "batch_id": str(batch.id),
            "claim_code": claim_code,
            "certificate_number": cert_num,
            "dynamic_values": {
                "nama": p.name,
                "nama_peserta": p.name,
                "institusi": a.institution,
                "peran": p.role,
                "judul_paper": p.paper_title or "",
            }
        }
        kafka_service.send_job(kafka_payload)
        dispatched += 1

    db.commit()
    db.refresh(batch)

    return {
        "message": f"Berhasil mengirim {dispatched} sertifikat dari presensi ke antrean Kafka.",
        "batch_id": batch.id,
        "total_dispatched": dispatched
    }
