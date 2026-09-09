"""
Special Roles & Committee Certificate Issuance Router
Handles dynamic role issuance (e.g. Committee, Reviewer, Session Chair, Cleaning Service, etc.)
Allows organizers to bulk issue certificates, bind specific templates, and dispatch claim codes via email.
"""

import uuid
import io
import re
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import pandas as pd
from pydantic import BaseModel, EmailStr, Field
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, status, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Event, Template, Participant, Certificate, User
from app.services import generate_claim_code
from app.services.email_service import email_service
from app.api.deps import get_current_user
from app.config import settings

router = APIRouter(prefix="/events", tags=["Special Roles & Committee Certificates"])


# ==============================================================================
# SCHEMAS
# ==============================================================================

class SpecialRoleRecipientItem(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    email: str = Field(..., max_length=255)
    institution: Optional[str] = Field(default="", max_length=255)
    role: Optional[str] = Field(default=None, max_length=100)


class SpecialRoleBulkRequest(BaseModel):
    role: str = Field(..., min_length=2, max_length=100)
    template_id: Optional[uuid.UUID] = None
    send_email: bool = True
    recipients: List[SpecialRoleRecipientItem]


class SpecialRoleItemResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    role: str
    institution: Optional[str] = ""
    claim_code: str
    certificate_number: str
    template_id: Optional[uuid.UUID] = None
    template_name: Optional[str] = None
    status: str
    download_count: int
    created_at: datetime
    cert_url: str


class SpecialRoleBulkResponse(BaseModel):
    success: bool
    role: str
    created_count: int
    skipped_count: int
    errors: List[str]
    items: List[SpecialRoleItemResponse]


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def normalize_col(header: str) -> str:
    cleaned = str(header).strip().lower()
    cleaned = re.sub(r"[^\w\s]", "", cleaned)
    return re.sub(r"\s+", "_", cleaned)


# ==============================================================================
# ENDPOINTS
# ==============================================================================

@router.get("/{event_id}/special-roles", response_model=List[SpecialRoleItemResponse])
def list_special_role_recipients(
    event_id: uuid.UUID,
    role: Optional[str] = Query(None, description="Filter by specific role name"),
    search: Optional[str] = Query(None, description="Search by name, email, or claim code"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists participants and their certificates for special roles in the given event.
    Special roles include Committee, Reviewer, Session Chair, Cleaning Service, etc.
    """
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == current_user.id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Acara tidak ditemukan.")

    query = db.query(Participant).join(Certificate, Certificate.participant_id == Participant.id)\
        .filter(Participant.event_id == event_id)

    # Exclude standard public attendance check-in roles if not explicitly matching custom_data
    # But include any participant having is_special_role or having roles outside Participant/Attendee
    if role and role.strip():
        query = query.filter(Participant.role.ilike(f"%{role.strip()}%"))
    else:
        # Default: show special roles or participants tagged with is_special_role
        # Or participants whose role is not 'Participant'/'Peserta'/'Attendee'
        query = query.filter(
            (Participant.role.notin_(["Participant", "Peserta", "Attendee"])) |
            (Participant.custom_data["is_special_role"].astext == "true")
        )

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            (Participant.name.ilike(term)) |
            (Participant.email.ilike(term)) |
            (Certificate.claim_code.ilike(term)) |
            (Certificate.certificate_number.ilike(term))
        )

    participants = query.order_by(Participant.created_at.desc()).all()

    templates_by_id = {t.id: t.name for t in event.templates}

    results = []
    for p in participants:
        cert = p.certificate
        if not cert:
            continue
        cust = p.custom_data or {}
        t_id = cert.template_id
        t_name = templates_by_id.get(t_id) if t_id else (event.template.name if event.template else None)

        results.append(SpecialRoleItemResponse(
            id=p.id,
            name=p.name,
            email=p.email,
            role=p.role,
            institution=cust.get("institution", ""),
            claim_code=cert.claim_code,
            certificate_number=cert.certificate_number,
            template_id=t_id,
            template_name=t_name,
            status=cert.status,
            download_count=cert.download_count,
            created_at=cert.created_at,
            cert_url=f"/verify/{cert.claim_code}"
        ))

    return results


@router.post("/{event_id}/special-roles/bulk", response_model=SpecialRoleBulkResponse, status_code=status.HTTP_201_CREATED)
def bulk_issue_special_roles(
    event_id: uuid.UUID,
    req: SpecialRoleBulkRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Bulk issues certificates for a custom role (e.g. Committee, Reviewer, Cleaning Service).
    Creates Participant & Certificate records, generates unique claim codes, and sends email notifications.
    """
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == current_user.id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Acara tidak ditemukan.")

    if not req.recipients:
        raise HTTPException(status_code=400, detail="Daftar penerima tidak boleh kosong.")

    # 1. Resolve target certificate template
    target_template_id = req.template_id
    chosen_template = None
    if target_template_id:
        chosen_template = db.query(Template).filter(Template.id == target_template_id, Template.event_id == event_id).first()
        if not chosen_template:
            raise HTTPException(status_code=400, detail="Template sertifikat yang dipilih tidak ditemukan pada acara ini.")
    else:
        # Try matching by role_target or template name
        for t in event.templates:
            if t.role_target and t.role_target.lower() == req.role.lower():
                chosen_template = t
                target_template_id = t.id
                break
        if not chosen_template:
            for t in event.templates:
                if t.name and t.name.lower() == req.role.lower():
                    chosen_template = t
                    target_template_id = t.id
                    break
        if not chosen_template and event.template:
            chosen_template = event.template
            target_template_id = event.template.id

    created_items = []
    skipped_count = 0
    errors = []

    for item in req.recipients:
        name_clean = item.name.strip()
        email_clean = item.email.strip().lower()
        item_role = (item.role.strip() if item.role and item.role.strip() else req.role.strip())

        if not name_clean or not email_clean or "@" not in email_clean:
            errors.append(f"Penerima '{name_clean}' ({email_clean}): Format nama atau email tidak valid.")
            skipped_count += 1
            continue

        # Check duplicate for this event and role
        existing_p = db.query(Participant).filter(
            Participant.event_id == event_id,
            Participant.email == email_clean,
            Participant.role == item_role
        ).first()
        if existing_p and existing_p.certificate:
            # Already issued, skip duplicate
            skipped_count += 1
            continue

        # Generate unique claim code
        claim_code = generate_claim_code()
        while db.query(Certificate).filter(Certificate.claim_code == claim_code).first():
            claim_code = generate_claim_code()

        # Certificate numbering
        if event.cert_prefix and event.cert_prefix.strip():
            prefix = event.cert_prefix.strip().upper()
            cert_num = f"{prefix}-{claim_code}"
        else:
            default_prefix = event.name[:4].upper().replace(" ", "C")
            cert_num = f"{default_prefix}-{datetime.now().year}-{claim_code}"

        # Create Participant
        participant = Participant(
            event_id=event_id,
            name=name_clean,
            email=email_clean,
            role=item_role,
            paper_title=None,
            custom_data={
                "institution": (item.institution or "").strip(),
                "is_special_role": True,
                "issued_by_user_id": str(current_user.id)
            }
        )
        db.add(participant)
        db.flush()

        # Create Certificate
        certificate = Certificate(
            event_id=event_id,
            participant_id=participant.id,
            template_id=target_template_id,
            certificate_number=cert_num,
            claim_code=claim_code,
            status="GENERATED",
            download_count=0
        )
        db.add(certificate)
        db.flush()

        # Dispatch background email
        if req.send_email and settings.SMTP_ENABLED:
            background_tasks.add_task(
                email_service.send_special_role_claim_email,
                to_email=email_clean,
                full_name=name_clean,
                event_name=event.name,
                claim_code=claim_code,
                role=item_role
            )

        created_items.append(SpecialRoleItemResponse(
            id=participant.id,
            name=participant.name,
            email=participant.email,
            role=participant.role,
            institution=item.institution or "",
            claim_code=claim_code,
            certificate_number=cert_num,
            template_id=target_template_id,
            template_name=chosen_template.name if chosen_template else None,
            status="GENERATED",
            download_count=0,
            created_at=datetime.now(timezone.utc),
            cert_url=f"/verify/{claim_code}"
        ))

    db.commit()

    return SpecialRoleBulkResponse(
        success=True,
        role=req.role,
        created_count=len(created_items),
        skipped_count=skipped_count,
        errors=errors,
        items=created_items
    )


@router.post("/{event_id}/special-roles/upload", response_model=SpecialRoleBulkResponse, status_code=status.HTTP_201_CREATED)
async def upload_special_roles_file(
    event_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    role: str = Form("Committee"),
    template_id: Optional[uuid.UUID] = Form(None),
    send_email: bool = Form(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Parses an uploaded Excel (.xlsx, .xls) or CSV spreadsheet and issues special role certificates.
    Accepts columns: Nama / Name, Email, and optional Institusi / Institution, Peran / Role.
    """
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == current_user.id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Acara tidak ditemukan.")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="File yang diunggah kosong.")

    filename = file.filename.lower()
    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file_bytes), dtype=str)
        elif filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(file_bytes), dtype=str)
        else:
            raise HTTPException(status_code=400, detail="Format file tidak didukung. Harap gunakan file .xlsx, .xls, atau .csv.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal membaca file spreadsheet: {str(e)}")

    if df.empty:
        raise HTTPException(status_code=400, detail="File spreadsheet tidak berisi data.")

    df = df.fillna("")

    # Map column headers
    col_map = {}
    for c in df.columns:
        nc = normalize_col(c)
        if nc in ["nama", "name", "full_name", "nama_lengkap", "peserta", "penerima"]:
            col_map[c] = "nama"
        elif nc in ["email", "e_mail", "surel", "email_address"]:
            col_map[c] = "email"
        elif nc in ["institusi", "institution", "instansi", "afiliasi", "affiliation", "kampus", "organisasi"]:
            col_map[c] = "institusi"
        elif nc in ["peran", "role", "jabatan", "position"]:
            col_map[c] = "peran"

    df = df.rename(columns=col_map)

    if "nama" not in df.columns or "email" not in df.columns:
        raise HTTPException(
            status_code=400,
            detail=f"File wajib memiliki kolom 'Nama' dan 'Email'. Kolom yang terbaca: {', '.join(df.columns)}"
        )

    recipients = []
    for _, row in df.iterrows():
        nama = str(row.get("nama", "")).strip()
        email = str(row.get("email", "")).strip()
        inst = str(row.get("institusi", "")).strip()
        row_role = str(row.get("peran", "")).strip() or role

        if nama and email:
            recipients.append(SpecialRoleRecipientItem(
                name=nama,
                email=email,
                institution=inst,
                role=row_role
            ))

    bulk_req = SpecialRoleBulkRequest(
        role=role,
        template_id=template_id,
        send_email=send_email,
        recipients=recipients
    )

    return bulk_issue_special_roles(
        event_id=event_id,
        req=bulk_req,
        background_tasks=background_tasks,
        db=db,
        current_user=current_user
    )


@router.post("/{event_id}/special-roles/{participant_id}/resend-email")
def resend_special_role_claim_email(
    event_id: uuid.UUID,
    participant_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Resends the claim code notification email to a special role participant.
    """
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == current_user.id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Acara tidak ditemukan.")

    participant = db.query(Participant).filter(
        Participant.id == participant_id,
        Participant.event_id == event_id
    ).first()
    if not participant:
        raise HTTPException(status_code=404, detail="Data penerima sertifikat tidak ditemukan.")

    cert = participant.certificate
    if not cert:
        raise HTTPException(status_code=400, detail="Sertifikat belum diterbitkan untuk penerima ini.")

    if not participant.email or "@" not in participant.email:
        raise HTTPException(status_code=400, detail="Email penerima tidak valid.")

    if not settings.SMTP_ENABLED:
        raise HTTPException(status_code=400, detail="Fitur SMTP sedang dinonaktifkan di konfigurasi server.")

    background_tasks.add_task(
        email_service.send_special_role_claim_email,
        to_email=participant.email,
        full_name=participant.name,
        event_name=event.name,
        claim_code=cert.claim_code,
        role=participant.role
    )

    return {
        "success": True,
        "message": f"Email kode klaim berhasil dijadwalkan untuk dikirim ulang ke {participant.email}."
    }


@router.delete("/{event_id}/special-roles/{participant_id}", status_code=status.HTTP_200_OK)
def delete_special_role_participant(
    event_id: uuid.UUID,
    participant_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Deletes a special role participant and their associated certificate.
    """
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == current_user.id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Acara tidak ditemukan.")

    participant = db.query(Participant).filter(
        Participant.id == participant_id,
        Participant.event_id == event_id
    ).first()
    if not participant:
        raise HTTPException(status_code=404, detail="Data penerima tidak ditemukan.")

    db.delete(participant)
    db.commit()

    return {
        "success": True,
        "message": f"Data penerima '{participant.name}' ({participant.role}) berhasil dihapus."
    }
