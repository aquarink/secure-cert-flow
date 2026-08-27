"""
Public-Facing Claiming and Verification System
Allows participants to verify authentic certificates via 8-char code or QR scan.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
import io
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Certificate, Participant, Event
from app.schemas.certificate import CertificateVerificationResponse
from app.schemas.claim import ClaimRequest, ClaimResponse
from app.services.minio_service import minio_service
from app.config import settings

router = APIRouter(tags=["Public Claim & Verification"])


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
            message="Kode sertifikat tidak ditemukan dalam sistem resmi kami. Waspada terhadap potensi pemalsuan!"
        )

    if cert.status != "GENERATED" and cert.status != "CLAIMED":
        return CertificateVerificationResponse(
            is_valid=False,
            certificate_number=cert.certificate_number,
            status=cert.status,
            message=f"Sertifikat sedang dalam status '{cert.status}' dan belum siap diverifikasi."
        )

    p = cert.participant
    ev = cert.event

    return CertificateVerificationResponse(
        is_valid=True,
        certificate_number=cert.certificate_number,
        claim_code=cert.claim_code,
        participant_name=p.name if p else "",
        participant_role=p.role if p else "",
        paper_title=p.paper_title if p else None,
        event_name=ev.name if ev else "",
        event_location=ev.location if ev else "",
        event_date=ev.event_date.strftime("%d %B %Y") if ev and ev.event_date else "",
        image_url=f"/api/v1/claim/{cert.claim_code}/image",
        checksum_sha256=cert.checksum_sha256,
        status=cert.status,
        message="Sertifikat RESMI dan ASLI terverifikasi pada sistem Secure Cert Flow."
    )


@router.post("/claim", response_model=ClaimResponse)
def claim_certificate(request: ClaimRequest, db: Session = Depends(get_db)):
    """
    Public claiming endpoint: Participant enters 8-character unique claim code.
    Marks certificate as CLAIMED and returns image preview & download links.
    """
    code_cleaned = request.claim_code.strip().upper()
    cert = db.query(Certificate).filter(Certificate.claim_code == code_cleaned).first()

    if not cert:
        raise HTTPException(
            status_code=404,
            detail="Kode klaim tidak ditemukan. Pastikan 8 karakter alfanumerik sudah benar."
        )

    if cert.status == "PENDING" or cert.status == "PROCESSING":
        raise HTTPException(
            status_code=400,
            detail="Sertifikat Anda sedang dalam proses generate di background queue. Silakan coba kembali dalam beberapa detik."
        )

    if cert.status == "FAILED":
        raise HTTPException(
            status_code=500,
            detail=f"Terjadi kendala saat men-generate sertifikat: {cert.error_message}. Harap hubungi panitia."
        )

    # Mark as claimed if first time
    if not cert.claimed_at:
        cert.claimed_at = datetime.now(timezone.utc)
        cert.status = "CLAIMED"
        db.commit()

    p = cert.participant
    ev = cert.event

    return ClaimResponse(
        success=True,
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
    """Streams certificate image directly from MinIO/Storage for public preview"""
    code_cleaned = claim_code.strip().upper()
    cert = db.query(Certificate).filter(Certificate.claim_code == code_cleaned).first()
    if not cert or not cert.image_url:
        raise HTTPException(status_code=404, detail="Gambar sertifikat tidak ditemukan.")

    if "/" in cert.image_url:
        bucket, obj_name = cert.image_url.split("/", 1)
    else:
        bucket = settings.MINIO_BUCKET_CERTIFICATES
        obj_name = cert.image_url

    try:
        data = minio_service.download_bytes(bucket, obj_name)
        return Response(content=data, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"File gambar gagal dimuat: {str(e)}")


@router.get("/claim/{claim_code}/download")
def download_certificate(claim_code: str, db: Session = Depends(get_db)):
    """Downloads certificate image attachment and increments download counter"""
    code_cleaned = claim_code.strip().upper()
    cert = db.query(Certificate).filter(Certificate.claim_code == code_cleaned).first()
    if not cert or not cert.image_url:
        raise HTTPException(status_code=404, detail="Sertifikat tidak ditemukan.")

    cert.download_count += 1
    db.commit()

    if "/" in cert.image_url:
        bucket, obj_name = cert.image_url.split("/", 1)
    else:
        bucket = settings.MINIO_BUCKET_CERTIFICATES
        obj_name = cert.image_url

    try:
        data = minio_service.download_bytes(bucket, obj_name)
        safe_filename = f"Sertifikat_{cert.certificate_number}.png"
        return StreamingResponse(
            io.BytesIO(data),
            media_type="image/png",
            headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'}
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"File gagal diunduh: {str(e)}")
