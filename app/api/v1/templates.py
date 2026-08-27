"""
Template & Placement Setup Endpoints
Handles naked certificate upload, signature upload, and visual coordinate configuration.
"""

import uuid
import io
from PIL import Image
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Event, Template, TemplateField, User, Certificate
from app.schemas.template import TemplateResponse, TemplateSetupRequest
from app.services.minio_service import minio_service
from app.services.cert_generator import cert_generator
from app.api.deps import get_current_user
from app.config import settings

router = APIRouter(prefix="/events", tags=["Templates & Placement Setup"])


@router.post("/{event_id}/template/upload-background", response_model=TemplateResponse)
async def upload_background_template(
    event_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Uploads a blank certificate background image (naked certificate) to MinIO.
    Detects image resolution (width x height) automatically.
    """
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == current_user.id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Acara tidak ditemukan.")

    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File harus berupa gambar (PNG/JPG/JPEG).")

    file_bytes = await file.read()
    try:
        pil_img = Image.open(io.BytesIO(file_bytes))
        width, height = pil_img.size
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"File gambar tidak valid: {str(e)}")

    # Upload to MinIO
    ext = file.filename.split(".")[-1] if "." in file.filename else "png"
    object_name = f"templates/{event_id}/background.{ext}"
    stored_path = minio_service.upload_bytes(
        bucket_name=settings.MINIO_BUCKET_TEMPLATES,
        object_name=object_name,
        data=file_bytes,
        content_type=file.content_type
    )

    template = db.query(Template).filter(Template.event_id == event_id).first()
    if not template:
        template = Template(
            event_id=event_id,
            background_image_url=stored_path,
            width=width,
            height=height,
            qr_x=width - 200,
            qr_y=height - 200,
            qr_size=150,
            cert_number_x=100,
            cert_number_y=height - 100,
        )
        db.add(template)
        db.flush()

        # Seed standard dynamic fields: nama, judul_paper, peran
        default_fields = [
            TemplateField(
                template_id=template.id,
                field_key="nama",
                label="Nama Peserta",
                pos_x=width // 2,
                pos_y=int(height * 0.45),
                font_size=48,
                font_color="#1E293B",
                text_align="center",
                is_required=True
            ),
            TemplateField(
                template_id=template.id,
                field_key="peran",
                label="Peran / Status",
                pos_x=width // 2,
                pos_y=int(height * 0.55),
                font_size=32,
                font_color="#475569",
                text_align="center",
                is_required=True
            ),
            TemplateField(
                template_id=template.id,
                field_key="judul_paper",
                label="Judul Makalah / Paper",
                pos_x=width // 2,
                pos_y=int(height * 0.65),
                font_size=28,
                font_color="#334155",
                text_align="center",
                is_required=False
            ),
        ]
        db.add_all(default_fields)
    else:
        template.background_image_url = stored_path
        template.width = width
        template.height = height

    db.commit()
    db.refresh(template)
    return template


@router.post("/{event_id}/template/upload-signature", response_model=TemplateResponse)
async def upload_signature(
    event_id: uuid.UUID,
    file: UploadFile = File(...),
    pos_x: int = Form(default=200),
    pos_y: int = Form(default=800),
    width: int = Form(default=220),
    height: int = Form(default=110),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Uploads a transparent PNG signature and sets its coordinates.
    """
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == current_user.id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Acara tidak ditemukan.")

    template = db.query(Template).filter(Template.event_id == event_id).first()
    if not template:
        raise HTTPException(
            status_code=400,
            detail="Harap unggah background sertifikat terlebih dahulu sebelum menambahkan tanda tangan.",
        )

    file_bytes = await file.read()
    ext = file.filename.split(".")[-1] if "." in file.filename else "png"
    object_name = f"signatures/{event_id}/signature.{ext}"

    stored_path = minio_service.upload_bytes(
        bucket_name=settings.MINIO_BUCKET_SIGNATURES,
        object_name=object_name,
        data=file_bytes,
        content_type=file.content_type or "image/png"
    )

    template.signature_image_url = stored_path
    template.signature_x = pos_x
    template.signature_y = pos_y
    template.signature_width = width
    template.signature_height = height

    db.commit()
    db.refresh(template)
    return template


@router.post("/{event_id}/template/setup", response_model=TemplateResponse)
def setup_template_layout(
    event_id: uuid.UUID,
    setup_data: TemplateSetupRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Saves visual coordinates for dynamic text fields, QR Code, and Auto-numbering.
    """
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == current_user.id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Acara tidak ditemukan.")

    template = db.query(Template).filter(Template.event_id == event_id).first()
    if not template:
        raise HTTPException(status_code=400, detail="Template belum diinisialisasi. Unggah gambar background dahulu.")

    # Update template coordinate fields
    if setup_data.width:
        template.width = setup_data.width
    if setup_data.height:
        template.height = setup_data.height
    if setup_data.signature_x is not None:
        template.signature_x = setup_data.signature_x
    if setup_data.signature_y is not None:
        template.signature_y = setup_data.signature_y
    if setup_data.signature_width is not None:
        template.signature_width = setup_data.signature_width
    if setup_data.signature_height is not None:
        template.signature_height = setup_data.signature_height
    if setup_data.qr_x is not None:
        template.qr_x = setup_data.qr_x
    if setup_data.qr_y is not None:
        template.qr_y = setup_data.qr_y
    if setup_data.qr_size is not None:
        template.qr_size = setup_data.qr_size
    if setup_data.cert_number_prefix:
        template.cert_number_prefix = setup_data.cert_number_prefix
    if setup_data.cert_number_x is not None:
        template.cert_number_x = setup_data.cert_number_x
    if setup_data.cert_number_y is not None:
        template.cert_number_y = setup_data.cert_number_y
    if setup_data.cert_number_font_size:
        template.cert_number_font_size = setup_data.cert_number_font_size
    if setup_data.cert_number_color:
        template.cert_number_color = setup_data.cert_number_color

    # Update dynamic field coordinates
    if setup_data.fields is not None:
        # Delete old fields and replace with updated coordinates
        db.query(TemplateField).filter(TemplateField.template_id == template.id).delete()
        for f in setup_data.fields:
            new_field = TemplateField(
                template_id=template.id,
                field_key=f.field_key.strip().lower(),
                label=f.label,
                pos_x=f.pos_x,
                pos_y=f.pos_y,
                font_family=f.font_family,
                font_size=f.font_size,
                font_color=f.font_color,
                text_align=f.text_align,
                max_width=f.max_width,
                is_required=f.is_required
            )
            db.add(new_field)

    # Auto-invalidate cached generated certificates for this event so they will re-render with latest placement on trigger
    db.query(Certificate).filter(Certificate.event_id == event_id).update({
        Certificate.image_url: None,
        Certificate.checksum_sha256: None
    })

    db.commit()
    db.refresh(template)
    return template


@router.get("/{event_id}/template", response_model=TemplateResponse)
def get_event_template(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieves current certificate layout template configuration"""
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == current_user.id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Acara tidak ditemukan.")

    if not event.template:
        raise HTTPException(status_code=404, detail="Template sertifikat untuk acara ini belum dibuat.")

    return event.template

from fastapi import Response

@router.post("/{event_id}/template/preview")
def preview_template_layout(
    event_id: uuid.UUID,
    setup_data: TemplateSetupRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Renders an instant live preview of the certificate layout with sample dummy values.
    Returns the rendered image as a PNG stream.
    """
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == current_user.id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Acara tidak ditemukan.")

    template = db.query(Template).filter(Template.event_id == event_id).first()
    if not template or not template.background_image_url:
        raise HTTPException(status_code=400, detail="Template sertifikat belum diunggah.")

    t_bucket, t_obj = template.background_image_url.split("/", 1) if "/" in template.background_image_url else (settings.MINIO_BUCKET_TEMPLATES, template.background_image_url)
    template_bytes = minio_service.download_bytes(t_bucket, t_obj)

    # Convert incoming fields
    fields_config = [
        {
            "field_key": f.field_key,
            "pos_x": f.pos_x,
            "pos_y": f.pos_y,
            "font_size": f.font_size,
            "font_color": f.font_color or "#1E293B",
            "font_family": f.font_family or "Cinzel-Bold.ttf",
            "text_align": f.text_align or "center"
        }
        for f in (setup_data.fields or [])
    ]

    sample_values = {
        "namalengkap": "Prof. Dr. Ahmad Farhan, M.Kom.",
        "nama_peserta": "Prof. Dr. Ahmad Farhan, M.Kom.",
        "nama": "Prof. Dr. Ahmad Farhan, M.Kom.",
        "institusi": "Fakultas Sains dan Teknologi, UIN Syarif Hidayatullah Jakarta",
        "institution": "Fakultas Sains dan Teknologi, UIN Syarif Hidayatullah Jakarta",
        "peran": "Presenter",
        "role": "Presenter",
        "judulpaper": "AI-Driven Blockchain Security in Multi-Cloud Infrastructure",
        "judul_paper": "AI-Driven Blockchain Security in Multi-Cloud Infrastructure",
        "kodepaper": "ICST-026",
        "kode_paper": "ICST-026",
        "namaacara": event.name,
        "nama_acara": event.name,
        "tanggalacara": event.event_date.strftime("%d %B %Y") if event.event_date else "10 September 2026",
        "tanggal_acara": event.event_date.strftime("%d %B %Y") if event.event_date else "10 September 2026",
        "lokasiacara": event.location or "Surabaya, Indonesia",
        "lokasi_acara": event.location or "Surabaya, Indonesia",
        "nomorsertifikat": f"{event.name[:4].upper().replace(' ', 'C')}-2026-SAMPLE26",
        "nomor_sertifikat": f"{event.name[:4].upper().replace(' ', 'C')}-2026-SAMPLE26",
        "kodeklaim": "SAMPLE26",
        "kode_klaim": "SAMPLE26",
    }

    qr_config = {
        "url": f"{settings.APP_BASE_URL}/verify/SAMPLE26",
        "pos_x": setup_data.qr_x if setup_data.qr_x is not None else 1700,
        "pos_y": setup_data.qr_y if setup_data.qr_y is not None else 860,
        "size": setup_data.qr_size or 150
    }

    cert_num_config = {
        "number": f"{event.name[:4].upper().replace(' ', 'C')}-2026-SAMPLE26",
        "pos_x": setup_data.cert_number_x if setup_data.cert_number_x is not None else 250,
        "pos_y": setup_data.cert_number_y if setup_data.cert_number_y is not None else 980,
        "font_size": setup_data.cert_number_font_size or 24,
        "color": setup_data.cert_number_color or "#475569"
    }

    rendered_bytes, _ = cert_generator.render(
        template_bytes=template_bytes,
        fields_config=fields_config,
        dynamic_values=sample_values,
        qr_config=qr_config,
        cert_number_config=cert_num_config
    )

    return Response(content=rendered_bytes, media_type="image/png")
