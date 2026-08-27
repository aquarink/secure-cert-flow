"""
Public-Facing Claiming and Verification System
Allows participants to verify authentic certificates via 8-char code or QR scan.
Supports Instant On-Demand Rendering and Panitia Release Controls.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
import io
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Certificate, Participant, Event, Template
from app.schemas.certificate import CertificateVerificationResponse
from app.schemas.claim import ClaimRequest, ClaimResponse
from app.services.minio_service import minio_service
from app.services.cert_generator import cert_generator
from app.config import settings

router = APIRouter(tags=["Public Claim & Verification"])


def ensure_certificate_rendered(cert: Certificate, db: Session) -> bytes:
    """
    Renders certificate on-demand if image is not yet cached in MinIO.
    """
    if cert.image_url:
        try:
            bucket, obj_name = cert.image_url.split("/", 1) if "/" in cert.image_url else (settings.MINIO_BUCKET_CERTIFICATES, cert.image_url)
            return minio_service.download_bytes(bucket, obj_name)
        except Exception:
            pass

    event = cert.event
    template = event.template if event else None
    if not template or not template.background_image_url:
        raise HTTPException(status_code=400, detail="Template sertifikat untuk acara ini belum diunggah panitia.")

    t_bucket, t_obj = template.background_image_url.split("/", 1) if "/" in template.background_image_url else (settings.MINIO_BUCKET_TEMPLATES, template.background_image_url)
    template_bytes = minio_service.download_bytes(t_bucket, t_obj)

    p = cert.participant
    custom_data = p.custom_data if (p and p.custom_data and isinstance(p.custom_data, dict)) else {}
    inst = custom_data.get("institution", "")
    p_code = custom_data.get("paper_code", "")

    fields_config = [
        {
            "field_key": f.field_key,
            "pos_x": f.pos_x,
            "pos_y": f.pos_y,
            "font_size": f.font_size,
            "font_color": f.font_color or "#1E293B",
            "text_align": f.text_align or "center"
        }
        for f in template.fields
    ]

    dynamic_values = {
        # Participant & Attendance fields
        "namalengkap": p.name if p else "",
        "nama_peserta": p.name if p else "",
        "nama": p.name if p else "",
        "institusi": inst,
        "institution": inst,
        "peran": p.role if p else "Participant",
        "role": p.role if p else "Participant",

        # Paper catalog fields
        "judulpaper": p.paper_title if p and p.paper_title else "",
        "judul_paper": p.paper_title if p and p.paper_title else "",
        "kodepaper": p_code,
        "kode_paper": p_code,

        # Event fields
        "namaacara": event.name if event else "",
        "nama_acara": event.name if event else "",
        "tanggalacara": event.event_date.strftime("%d %B %Y") if event and event.event_date else "",
        "tanggal_acara": event.event_date.strftime("%d %B %Y") if event and event.event_date else "",
        "lokasiacara": event.location if event else "",
        "lokasi_acara": event.location if event else "",

        # Meta fields
        "nomorsertifikat": cert.certificate_number,
        "nomor_sertifikat": cert.certificate_number,
        "kodeklaim": cert.claim_code,
        "kode_klaim": cert.claim_code,
    }

    qr_config = {
        "url": f"{settings.APP_BASE_URL}/verify/{cert.claim_code}",
        "pos_x": template.qr_x if template.qr_x is not None else 1700,
        "pos_y": template.qr_y if template.qr_y is not None else 860,
        "size": template.qr_size or 150
    }

    cert_num_config = {
        "number": cert.certificate_number,
        "pos_x": template.cert_number_x if template.cert_number_x is not None else 250,
        "pos_y": template.cert_number_y if template.cert_number_y is not None else 980,
        "font_size": template.cert_number_font_size or 24,
        "color": template.cert_number_color or "#475569"
    }

    rendered_bytes, checksum = cert_generator.render(
        template_bytes=template_bytes,
        fields_config=fields_config,
        dynamic_values=dynamic_values,
        qr_config=qr_config,
        cert_number_config=cert_num_config
    )

    out_obj = f"certs/{event.id}/{cert.claim_code}.png"
    cert_url = minio_service.upload_bytes(settings.MINIO_BUCKET_CERTIFICATES, out_obj, rendered_bytes, "image/png")

    cert.image_url = cert_url
    cert.checksum_sha256 = checksum
    cert.status = "GENERATED"
    db.commit()

    return rendered_bytes


@router.get("/verify/{claim_code}", response_model=CertificateVerificationResponse)
def verify_certificate(claim_code: str, db: Session = Depends(get_db)):
    """
    Public verification endpoint (target of certificate QR Codes).
    Validates certificate authenticity, displaying recipient details and SHA-256 hash.
    """
    code_cleaned = claim_code.strip().upper()
    cert = db.query(Certificate).filter(Certificate.claim_code == code_cleaned).first()
    
    if not cert:
        return CertificateVerificationResponse(
            is_valid=False,
            is_cert_open=False,
            message="Kode sertifikat tidak ditemukan dalam sistem resmi kami. Waspada terhadap potensi pemalsuan!"
        )

    p = cert.participant
    ev = cert.event
    is_open = bool(ev.is_cert_open) if ev else False

    # Ensure certificate image is ready
    if not cert.image_url and ev and ev.template and ev.template.background_image_url:
        try:
            ensure_certificate_rendered(cert, db)
        except Exception:
            pass

    msg = "Sertifikat RESMI dan ASLI terverifikasi pada sistem Secure Cert Flow."
    if not is_open:
        msg = "Data kehadiran & sertifikat Anda terverifikasi secara sah. Unduh sertifikat akan dibuka oleh panitia setelah sesi acara berakhir."

    return CertificateVerificationResponse(
        is_valid=True,
        is_cert_open=is_open,
        certificate_number=cert.certificate_number,
        claim_code=cert.claim_code,
        participant_name=p.name if p else "",
        participant_role=p.role if p else "",
        paper_title=p.paper_title if p else None,
        event_name=ev.name if ev else "",
        event_location=ev.location if ev else "",
        event_date=ev.event_date.strftime("%d %B %Y") if ev and ev.event_date else "",
        image_url=f"/api/v1/claim/{cert.claim_code}/image" if is_open else None,
        checksum_sha256=cert.checksum_sha256 if is_open else None,
        status=cert.status,
        message=msg
    )


@router.post("/claim", response_model=ClaimResponse)
def claim_certificate(request: ClaimRequest, db: Session = Depends(get_db)):
    """
    Public claiming endpoint: Participant enters 8-character unique claim code.
    """
    code_cleaned = request.claim_code.strip().upper()
    cert = db.query(Certificate).filter(Certificate.claim_code == code_cleaned).first()

    if not cert:
        raise HTTPException(
            status_code=404,
            detail="Kode klaim tidak ditemukan. Pastikan 8 karakter alfanumerik sudah benar."
        )

    ev = cert.event
    p = cert.participant
    is_open = bool(ev.is_cert_open) if ev else False

    if not is_open:
        return ClaimResponse(
            success=True,
            is_cert_open=False,
            message="Data kehadiran Anda telah tercatat sah! Unduh sertifikat resmi akan dibuka oleh panitia setelah acara berakhir.",
            certificate_number=cert.certificate_number,
            participant_name=p.name if p else "",
            event_name=ev.name if ev else "",
            event_date=ev.event_date.strftime("%d %B %Y") if ev and ev.event_date else "",
            image_url=None,
            download_url=None,
            checksum_sha256=None
        )

    # Ensure on-demand render
    if not cert.image_url:
        ensure_certificate_rendered(cert, db)

    # Mark as claimed if first time
    if not cert.claimed_at:
        cert.claimed_at = datetime.now(timezone.utc)
        cert.status = "CLAIMED"
        db.commit()

    return ClaimResponse(
        success=True,
        is_cert_open=True,
        message="Sertifikat berhasil diklaim!",
        certificate_number=cert.certificate_number,
        participant_name=p.name if p else "",
        event_name=ev.name if ev else "",
        event_date=ev.event_date.strftime("%d %B %Y") if ev and ev.event_date else "",
        image_url=f"/api/v1/claim/{cert.claim_code}/image",
        download_url=f"/api/v1/claim/{cert.claim_code}/download",
        checksum_sha256=cert.checksum_sha256
    )


@router.get("/claim/{claim_code}/image")
def get_certificate_image(claim_code: str, db: Session = Depends(get_db)):
    """Streams certificate image directly with on-demand rendering"""
    code_cleaned = claim_code.strip().upper()
    cert = db.query(Certificate).filter(Certificate.claim_code == code_cleaned).first()
    if not cert:
        raise HTTPException(status_code=404, detail="Sertifikat tidak ditemukan.")

    data = ensure_certificate_rendered(cert, db)
    return Response(content=data, media_type="image/png")


@router.get("/claim/{claim_code}/download")
def download_certificate(claim_code: str, db: Session = Depends(get_db)):
    """Downloads certificate image attachment and increments download counter"""
    code_cleaned = claim_code.strip().upper()
    cert = db.query(Certificate).filter(Certificate.claim_code == code_cleaned).first()
    if not cert:
        raise HTTPException(status_code=404, detail="Sertifikat tidak ditemukan.")

    ev = cert.event
    if ev and not ev.is_cert_open:
        raise HTTPException(
            status_code=403,
            detail="Unduh sertifikat untuk acara ini belum dibuka oleh panitia. Harap menunggu hingga sesi acara selesai."
        )

    data = ensure_certificate_rendered(cert, db)
    cert.download_count += 1
    db.commit()

    safe_filename = f"Sertifikat_{cert.certificate_number}.png"
    return StreamingResponse(
        io.BytesIO(data),
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'}
    )
