"""
Attendance Management API Router
Handles live check-in with camera selfie capture, geolocation, IP logging, and instant on-demand certificate assignment.
"""

import io
import os
import re
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


def clean_name_tokens(name: str) -> list[str]:
    """Strips academic titles, degrees, and special characters to extract essential name tokens"""
    if not name:
        return []
    s = name.lower()
    titles_pattern = r'\b(prof|dr|dra|drs|ir|apt|phd|ph\.d|msc|m\.sc|mkom|m\.kom|skom|s\.kom|mt|m\.t|st|s\.t|mcs|m\.cs|msi|m\.si|ssi|s\.si|mpd|m\.pd|spd|s\.pd|meng|m\.eng|beng|b\.eng|bsc|b\.sc|ba|b\.a|ma|m\.a|llm|ll\.m|sh|s\.h|mh|m\.h|se|s\.e|mm|m\.m|akt|ak|h|hj|kh)\b'
    s = re.sub(titles_pattern, ' ', s)
    s = re.sub(r'[^a-z\s]', ' ', s)
    return [w for w in s.split() if len(w) >= 2]


def parse_paper_authors(authors_str: str) -> list[str]:
    """Splits author names separated by commas, semicolons, and, &, or newlines"""
    if not authors_str:
        return []
    s = re.sub(r'\s+(and|&)\s+', ',', authors_str, flags=re.IGNORECASE)
    parts = re.split(r'[,;\n\r]+', s)
    return [p.strip() for p in parts if p.strip()]


def match_author_name(input_name: str, author_list: list[str]) -> tuple[bool, Optional[str]]:
    """Checks if input_name matches any author in author_list"""
    if not input_name or not author_list:
        return False, None

    input_tokens = set(clean_name_tokens(input_name))
    if not input_tokens:
        return False, None

    for author in author_list:
        author_tokens = set(clean_name_tokens(author))
        if not author_tokens:
            continue
        if input_tokens == author_tokens:
            return True, author
        common = input_tokens.intersection(author_tokens)
        if len(common) >= 2:
            return True, author
        if len(input_tokens) == 1 and len(common) == 1:
            if len(author_tokens) == 1:
                return True, author
            first_token = list(input_tokens)[0]
            if len(first_token) >= 4 and first_token in author_tokens:
                return True, author

    return False, None


def is_name_match(name1: str, name2: str) -> bool:
    """Helper to check if two person names match (handling titles/degrees)"""
    tokens1 = set(clean_name_tokens(name1))
    tokens2 = set(clean_name_tokens(name2))
    if not tokens1 or not tokens2:
        return False
    if tokens1 == tokens2:
        return True
    common = tokens1.intersection(tokens2)
    if len(common) >= 2:
        return True
    if (len(tokens1) == 1 or len(tokens2) == 1) and len(common) == 1:
        single = list(tokens1 if len(tokens1) == 1 else tokens2)[0]
        if len(single) >= 4:
            return True
    return False


def verify_author_paper_status(db: Session, event_id: uuid.UUID, paper: Paper, full_name: str) -> dict:
    """
    Validates:
    1. If full_name exists in paper's author list.
    2. If this Paper ID + Author has already been checked in or claimed.
    """
    author_list = parse_paper_authors(paper.authors or "")
    
    if not full_name or not full_name.strip():
        return {
            "status": "NAME_REQUIRED",
            "is_valid": False,
            "is_claimed": False,
            "matched_author": None,
            "author_list": author_list,
            "message": "Silakan isi Nama Lengkap & Gelar Anda terlebih dahulu."
        }

    is_match, matched_author = match_author_name(full_name, author_list)
    if not is_match:
        authors_display = ", ".join(author_list) if author_list else (paper.authors or "-")
        return {
            "status": "NAME_MISMATCH",
            "is_valid": False,
            "is_claimed": False,
            "matched_author": None,
            "author_list": author_list,
            "message": f"Nama '{full_name}' tidak terdaftar sebagai penulis pada Paper ID {paper.paper_code or ''}. Daftar Penulis: {authors_display}. Pastikan nama yang Anda masukkan sesuai dengan nama penulis di paper."
        }

    # Check if this author has already checked in or claimed
    # 1. Check Attendance table for this paper
    existing_attendances = db.query(Attendance).filter(
        Attendance.event_id == event_id,
        Attendance.paper_id == paper.id,
        Attendance.role == "Author"
    ).all()

    for att in existing_attendances:
        if is_name_match(full_name, att.full_name) or (matched_author and is_name_match(matched_author, att.full_name)):
            p = db.query(Participant).filter(
                Participant.event_id == event_id,
                Participant.name == att.full_name,
                Participant.role == "Author"
            ).order_by(Participant.created_at.desc()).first()
            claim_code = p.certificate.claim_code if (p and p.certificate) else None
            return {
                "status": "ALREADY_CLAIMED",
                "is_valid": False,
                "is_claimed": True,
                "matched_author": matched_author,
                "author_list": author_list,
                "claim_code": claim_code,
                "message": f"Paper ID ({paper.paper_code or ''}) untuk Author ({matched_author or full_name}) sudah pernah didaftarkan / diklaim. Silakan ke https://sertifikat.uinjakarta.id/claim dan masukkan kode yang Anda terima pada saat mendaftar."
            }

    # 2. Check Participant records for this paper (direct participant or legacy)
    existing_participants = db.query(Participant).filter(
        Participant.event_id == event_id,
        Participant.role == "Author"
    ).all()

    for p in existing_participants:
        p_code = p.custom_data.get("paper_code") if (p.custom_data and isinstance(p.custom_data, dict)) else None
        if p.paper_title == paper.title or (paper.paper_code and p_code == paper.paper_code):
            if is_name_match(full_name, p.name) or (matched_author and is_name_match(matched_author, p.name)):
                claim_code = p.certificate.claim_code if p.certificate else None
                return {
                    "status": "ALREADY_CLAIMED",
                    "is_valid": False,
                    "is_claimed": True,
                    "matched_author": matched_author,
                    "author_list": author_list,
                    "claim_code": claim_code,
                    "message": f"Paper ID ({paper.paper_code or ''}) untuk Author ({matched_author or full_name}) sudah pernah didaftarkan / diklaim. Silakan ke https://sertifikat.uinjakarta.id/claim dan masukkan kode yang Anda terima pada saat mendaftar."
                }

    return {
        "status": "OK",
        "is_valid": True,
        "is_claimed": False,
        "matched_author": matched_author,
        "author_list": author_list,
        "message": f"Nama terverifikasi sah sebagai penulis: {matched_author}."
    }


@router.get("/events/{event_id}/attendance/check-author")
def check_author_status_endpoint(
    event_id: uuid.UUID,
    paper_code: Optional[str] = None,
    paper_id: Optional[uuid.UUID] = None,
    full_name: str = Query("", description="Nama lengkap peserta"),
    db: Session = Depends(get_db)
):
    """
    Real-time validation endpoint:
    Checks if full_name is in the paper's author list and whether Paper ID + Author has already been claimed.
    """
    paper_obj = None
    if paper_id:
        paper_obj = db.query(Paper).filter(Paper.id == paper_id, Paper.event_id == event_id).first()
    elif paper_code and paper_code.strip():
        code_clean = paper_code.strip()
        paper_obj = db.query(Paper).filter(
            Paper.event_id == event_id,
            func.lower(Paper.paper_code) == code_clean.lower()
        ).first()

    if not paper_obj:
        return {
            "status": "NOT_FOUND",
            "is_valid": False,
            "is_claimed": False,
            "matched_author": None,
            "author_list": [],
            "message": "Paper ID / Kode Paper tidak ditemukan di Katalog Judul Paper acara ini."
        }

    res = verify_author_paper_status(db, event_id, paper_obj, full_name)
    res["paper"] = {
        "id": str(paper_obj.id),
        "paper_code": paper_obj.paper_code or "",
        "title": paper_obj.title,
        "authors": paper_obj.authors or ""
    }
    return res


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

    # Strict validation: Author MUST have a valid registered paper, match author list, and not already claimed
    if check_in.role == "Author":
        if not paper_obj:
            raise HTTPException(
                status_code=400,
                detail="Paper ID / Kode Paper tidak ditemukan di Katalog Judul Paper acara ini. Pastikan Paper ID Anda sudah terdaftar."
            )
        author_check = verify_author_paper_status(db, event_id, paper_obj, check_in.full_name)
        if author_check["status"] != "OK":
            raise HTTPException(
                status_code=400,
                detail=author_check["message"]
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
