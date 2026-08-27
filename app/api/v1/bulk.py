"""
Bulk Import & Background Processing Endpoints (Kafka Integration)
Dispatches certificate generation tasks to Kafka broker and provides progress tracking.
"""

import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, status
from sqlalchemy.orm import Session
from app.database import get_db, SessionLocal
from app.models import Event, Template, Participant, Certificate, Batch, User
from app.schemas.batch import BatchResponse, BatchProgressResponse
from app.services import excel_service, kafka_service, generate_claim_code
from app.worker.kafka_consumer import CertificateConsumerWorker
from app.api.deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/events", tags=["Bulk Import & Kafka Processing"])


def run_local_worker_fallback(batch_id: uuid.UUID):
    """
    Fallback worker executing queued jobs directly if Kafka daemon is in local mode.
    Ensures 100% testability and reliability in all network configurations.
    """
    db = SessionLocal()
    try:
        worker = CertificateConsumerWorker()
        certs = db.query(Certificate).filter(
            Certificate.batch_id == batch_id,
            Certificate.status == "PENDING"
        ).all()
        
        for cert in certs:
            participant = cert.participant
            dynamic_values = {
                "nama": participant.name,
                "peran": participant.role,
                "judul_paper": participant.paper_title or "",
                "email": participant.email,
                **participant.custom_data
            }
            payload = {
                "certificate_id": str(cert.id),
                "event_id": str(cert.event_id),
                "batch_id": str(batch_id),
                "participant_id": str(participant.id),
                "claim_code": cert.claim_code,
                "certificate_number": cert.certificate_number,
                "dynamic_values": dynamic_values
            }
            worker.process_certificate_job(db, payload)
    finally:
        db.close()


@router.post("/{event_id}/import", response_model=BatchResponse, status_code=status.HTTP_202_ACCEPTED)
async def import_participants_and_generate(
    event_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Uploads Excel/CSV spreadsheet with recipient list.
    Validates required columns, creates database records, and enqueues jobs to Kafka.
    """
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == current_user.id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Acara tidak ditemukan.")

    template = db.query(Template).filter(Template.event_id == event_id).first()
    if not template:
        raise HTTPException(
            status_code=400,
            detail="Template sertifikat belum diatur untuk acara ini. Harap atur template terlebih dahulu.",
        )

    file_bytes = await file.read()
    required_field_keys = [f.field_key for f in template.fields if f.is_required]

    # Parse and validate spreadsheet
    records, errors = excel_service.parse_file(
        file_bytes=file_bytes,
        filename=file.filename,
        required_fields=required_field_keys
    )

    if not records:
        raise HTTPException(
            status_code=400,
            detail={"message": "Gagal memproses file Excel/CSV", "errors": errors}
        )

    # 1. Create Batch record
    batch = Batch(
        event_id=event_id,
        filename=file.filename,
        total_records=len(records),
        processed_records=0,
        success_records=0,
        failed_records=0,
        status="processing",
        error_log=[]
    )
    db.add(batch)
    db.flush()

    kafka_messages = []
    prefix = template.cert_number_prefix or "CERT"

    # 2. Create Participant and Certificate records
    for idx, rec in enumerate(records):
        participant = Participant(
            event_id=event_id,
            batch_id=batch.id,
            email=rec["email"],
            name=rec["name"],
            role=rec["role"],
            paper_title=rec["paper_title"],
            custom_data=rec["custom_data"]
        )
        db.add(participant)
        db.flush()

        # Generate unique 8-character claim code & certificate serial number
        claim_code = generate_claim_code(8)
        cert_number = f"{prefix}-{datetime.now().strftime('%Y%m%d')}-{claim_code}"

        certificate = Certificate(
            event_id=event_id,
            participant_id=participant.id,
            batch_id=batch.id,
            certificate_number=cert_number,
            claim_code=claim_code,
            status="PENDING",
            download_count=0
        )
        db.add(certificate)
        db.flush()

        # Prepare Kafka message payload
        job_payload = {
            "certificate_id": str(certificate.id),
            "participant_id": str(participant.id),
            "event_id": str(event_id),
            "batch_id": str(batch.id),
            "claim_code": claim_code,
            "certificate_number": cert_number,
            "dynamic_values": rec["dynamic_values"],
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        kafka_messages.append(job_payload)

    db.commit()
    db.refresh(batch)

    # 3. Push jobs to Kafka topic (load leveling)
    kafka_dispatched = True
    for job in kafka_messages:
        success = kafka_service.send_certificate_job(job)
        if not success:
            kafka_dispatched = False

    # If Kafka broker was unreachable or direct processing triggered, execute fallback worker
    if not kafka_dispatched:
        logger.info("Kafka enqueue partial or fallback, triggering background worker task...")
        background_tasks.add_task(run_local_worker_fallback, batch.id)

    return batch


@router.get("/{event_id}/batch-progress/{batch_id}", response_model=BatchProgressResponse)
def get_batch_progress(
    event_id: uuid.UUID,
    batch_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Real-time progress query endpoint for TailAdmin UI progress bar.
    Returns: { "total": 30, "processed": 4, "percentage": 13.33, "status": "processing" }
    """
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == current_user.id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Acara tidak ditemukan.")

    batch = db.query(Batch).filter(Batch.id == batch_id, Batch.event_id == event_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch import tidak ditemukan.")

    return BatchProgressResponse(
        batch_id=batch.id,
        event_id=batch.event_id,
        status=batch.status,
        total=batch.total_records,
        processed=batch.processed_records,
        success=batch.success_records,
        failed=batch.failed_records,
        percentage=batch.progress_percentage,
        is_completed=batch.status in ["completed", "failed"]
    )
