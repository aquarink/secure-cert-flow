"""
Seed Script for Generating Sample/Test Data
Creates default organizer account, demo conference event, template layout, paper catalog, sample attendances, and certificates.

Usage:
    python scripts/seed_demo.py
"""

import sys
import os
import io
from datetime import date, datetime, timezone
from PIL import Image, ImageDraw

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import SessionLocal, engine, Base
from app.models import User, Event, Template, TemplateField, Participant, Certificate, Batch, Paper, Attendance
from app.services import hash_password, minio_service, cert_generator, generate_claim_code
from app.config import settings


def seed_database():
    db = SessionLocal()
    try:
        print("Creating demo test credentials and sample data...")

        # 1. Create Default Test Organizer Account
        test_email = "admin@uinjkt.ac.id"
        test_password = "AdminPassword123!"

        user = db.query(User).filter(User.email == test_email).first()
        if not user:
            user = User(
                email=test_email,
                hashed_password=hash_password(test_password),
                full_name="Administrator Sertifikat UIN",
                is_active=True,
                is_verified=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"Created Test User: {test_email}")
        else:
            user.hashed_password = hash_password(test_password)
            user.is_verified = True
            db.commit()
            print(f"Updated Test User: {test_email}")

        # 2. Create Demo Event
        event_name = "International Conference on Science & Technology (ICST 2026)"
        event = db.query(Event).filter(Event.user_id == user.id, Event.name == event_name).first()
        if not event:
            event = Event(
                user_id=user.id,
                name=event_name,
                location="Auditorium Utama UIN Syarif Hidayatullah Jakarta",
                event_date=date(2026, 8, 27),
                description="Konferensi internasional tahunan bidang sains, teknologi, dan kecerdasan buatan.",
                status="published"
            )
            db.add(event)
            db.commit()
            db.refresh(event)
            print(f"Created Demo Event: {event.name}")

        # 3. Create Sample Certificate Template Image
        canvas_w, canvas_h = 1920, 1080
        blank_img = Image.new("RGB", (canvas_w, canvas_h), color=(248, 250, 252))
        draw = ImageDraw.Draw(blank_img)
        # Decorative border
        draw.rectangle([(40, 40), (canvas_w - 40, canvas_h - 40)], outline=(30, 41, 59), width=6)
        draw.rectangle([(56, 56), (canvas_w - 56, canvas_h - 56)], outline=(99, 102, 241), width=2)
        # Header title banner
        draw.text((canvas_w // 2, 220), "SERTIFIKAT PENGHARGAAN", fill="#1E293B", font=cert_generator._get_font("DejaVuSans-Bold.ttf", 64), anchor="mm")
        draw.text((canvas_w // 2, 310), "Diberikan dengan hormat dan apresiasi setinggi-tingginya kepada:", fill="#64748B", font=cert_generator._get_font("DejaVuSans.ttf", 26), anchor="mm")
        draw.text((canvas_w // 2, 590), "Atas kontribusi dan partisipasi aktif sebagai:", fill="#64748B", font=cert_generator._get_font("DejaVuSans.ttf", 24), anchor="mm")
        draw.text((canvas_w // 2, 980), "International Conference on Science & Technology • UIN Syarif Hidayatullah Jakarta", fill="#94A3B8", font=cert_generator._get_font("DejaVuSans.ttf", 20), anchor="mm")

        img_buf = io.BytesIO()
        blank_img.save(img_buf, format="PNG", optimize=True)
        bg_bytes = img_buf.getvalue()

        # Upload template to storage
        bg_url = minio_service.upload_bytes(
            bucket_name=settings.MINIO_BUCKET_TEMPLATES,
            object_name=f"templates/{event.id}/demo_background.png",
            data=bg_bytes,
            content_type="image/png"
        )

        template = db.query(Template).filter(Template.event_id == event.id).first()
        if not template:
            template = Template(
                event_id=event.id,
                background_image_url=bg_url,
                width=canvas_w,
                height=canvas_h,
                qr_x=canvas_w - 220,
                qr_y=canvas_h - 220,
                qr_size=160,
                cert_number_prefix="ICST-2026",
                cert_number_x=100,
                cert_number_y=canvas_h - 100,
                cert_number_font_size=24,
                cert_number_color="#475569"
            )
            db.add(template)
            db.flush()

            # Add Template Dynamic Fields
            fields = [
                TemplateField(template_id=template.id, field_key="nama_peserta", label="Nama Peserta", pos_x=canvas_w // 2, pos_y=450, font_size=52, font_color="#1E293B", text_align="center", is_required=True),
                TemplateField(template_id=template.id, field_key="peran", label="Peran", pos_x=canvas_w // 2, pos_y=660, font_size=36, font_color="#4F46E5", text_align="center", is_required=True),
                TemplateField(template_id=template.id, field_key="judul_paper", label="Judul Paper", pos_x=canvas_w // 2, pos_y=770, font_size=28, font_color="#334155", text_align="center", is_required=False),
            ]
            db.add_all(fields)
            db.commit()
            db.refresh(template)
            print(f"Configured Template Layout for Event {event.name}")

        # 4. Create Sample Conference Papers Catalog
        sample_papers = [
            {
                "paper_code": "ICST-001",
                "title": "Scalable Kafka Architecture for Enterprise Microservices",
                "authors": "Dr. Ahmad Farhan, S.Kom., M.T.",
                "presenter_name": "Dr. Ahmad Farhan"
            },
            {
                "paper_code": "ICST-002",
                "title": "Automated Fraud Detection in Academic Certificates using SHA-256 and QR Verification",
                "authors": "Siti Nurhaliza, M.Cs., Prof. Alex Rivers",
                "presenter_name": "Siti Nurhaliza, M.Cs."
            },
            {
                "paper_code": "ICST-003",
                "title": "Natural Language Processing for Multi-Lingual Conference Transcripts",
                "authors": "Dr. Budi Pratama, Siti Aminah",
                "presenter_name": "Dr. Budi Pratama"
            }
        ]

        for p_data in sample_papers:
            p_obj = db.query(Paper).filter(Paper.event_id == event.id, Paper.paper_code == p_data["paper_code"]).first()
            if not p_obj:
                p_obj = Paper(
                    event_id=event.id,
                    paper_code=p_data["paper_code"],
                    title=p_data["title"],
                    authors=p_data["authors"],
                    presenter_name=p_data["presenter_name"]
                )
                db.add(p_obj)
        db.commit()
        print("Seeded Conference Papers Catalog.")

        # 5. Create Sample Live Selfie Attendance Records
        sample_selfie = Image.new("RGB", (320, 240), color=(40, 50, 70))
        d_selfie = ImageDraw.Draw(sample_selfie)
        d_selfie.ellipse([(110, 50), (210, 150)], fill=(200, 180, 160))
        d_selfie.rectangle([(80, 150), (240, 240)], fill=(70, 90, 140))
        d_selfie.text((160, 20), "LIVE VERIFIED SELFIE", fill=(255, 255, 255), anchor="mm")
        s_buf = io.BytesIO()
        sample_selfie.save(s_buf, format="JPEG")
        selfie_bytes = s_buf.getvalue()

        selfie_url = minio_service.upload_bytes(
            bucket_name=settings.MINIO_BUCKET_CERTIFICATES,
            object_name=f"attendances/{event.id}/demo_selfie.jpg",
            data=selfie_bytes,
            content_type="image/jpeg"
        )

        sample_attendances = [
            {
                "full_name": "Dr. Ahmad Farhan, S.Kom., M.T.",
                "institution": "UIN Syarif Hidayatullah Jakarta",
                "role": "Presenter",
                "paper_title": "Scalable Kafka Architecture for Enterprise Microservices",
                "lat": -6.3045,
                "long": 106.7554,
                "ip": "10.88.0.7"
            },
            {
                "full_name": "Siti Nurhaliza, M.Cs.",
                "institution": "FST UIN Syarif Hidayatullah",
                "role": "Author",
                "paper_title": "Automated Fraud Detection in Academic Certificates using SHA-256 and QR Verification",
                "lat": -6.3042,
                "long": 106.7558,
                "ip": "10.88.0.12"
            }
        ]

        for att_data in sample_attendances:
            att = db.query(Attendance).filter(Attendance.event_id == event.id, Attendance.full_name == att_data["full_name"]).first()
            if not att:
                att = Attendance(
                    event_id=event.id,
                    full_name=att_data["full_name"],
                    institution=att_data["institution"],
                    role=att_data["role"],
                    paper_title=att_data["paper_title"],
                    photo_url=selfie_url,
                    latitude=att_data["lat"],
                    longitude=att_data["long"],
                    accuracy_meters=10.5,
                    ip_address=att_data["ip"],
                    user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0"
                )
                db.add(att)
        db.commit()
        print("Seeded Sample Attendance Check-In Records.")

        # 6. Create Pre-generated Certificates with Fixed Claim Codes
        sample_participants = [
            {
                "name": "Dr. Ahmad Farhan, S.Kom., M.T.",
                "email": "ahmad.farhan@uinjkt.ac.id",
                "role": "Keynote Presenter",
                "paper_title": "Scalable Kafka Architecture for Enterprise Microservices",
                "claim_code": "DEMO2026",
            },
            {
                "name": "Siti Nurhaliza, M.Cs.",
                "email": "siti.nurhaliza@uinjkt.ac.id",
                "role": "Author",
                "paper_title": "Automated Fraud Detection in Academic Certificates using SHA-256 and QR Verification",
                "claim_code": "UINJ2026",
            },
            {
                "name": "Budi Santoso",
                "email": "budi.santoso@gmail.com",
                "role": "Attendee",
                "paper_title": "",
                "claim_code": "TEST8888",
            }
        ]

        for p_data in sample_participants:
            p = db.query(Participant).filter(Participant.event_id == event.id, Participant.email == p_data["email"]).first()
            if not p:
                p = Participant(
                    event_id=event.id,
                    name=p_data["name"],
                    email=p_data["email"],
                    role=p_data["role"],
                    paper_title=p_data["paper_title"],
                    custom_data={}
                )
                db.add(p)
                db.flush()

            cert = db.query(Certificate).filter(Certificate.participant_id == p.id).first()
            claim_code = p_data["claim_code"]
            cert_num = f"ICST-2026-{claim_code}"

            fields_config = [
                {"field_key": "nama_peserta", "pos_x": canvas_w // 2, "pos_y": 450, "font_size": 52, "font_color": "#1E293B", "text_align": "center"},
                {"field_key": "peran", "pos_x": canvas_w // 2, "pos_y": 660, "font_size": 36, "font_color": "#4F46E5", "text_align": "center"},
                {"field_key": "judul_paper", "pos_x": canvas_w // 2, "pos_y": 770, "font_size": 28, "font_color": "#334155", "text_align": "center"},
            ]
            dynamic_vals = {
                "nama_peserta": p.name,
                "peran": p.role,
                "judul_paper": p.paper_title or "",
            }
            qr_config = {
                "url": f"{settings.APP_BASE_URL}/verify/{claim_code}",
                "pos_x": canvas_w - 220,
                "pos_y": canvas_h - 220,
                "size": 160,
            }
            cert_num_config = {
                "number": cert_num,
                "pos_x": 100,
                "pos_y": canvas_h - 100,
                "font_size": 24,
                "color": "#475569",
            }

            rendered_bytes, checksum = cert_generator.render(
                template_bytes=bg_bytes,
                fields_config=fields_config,
                dynamic_values=dynamic_vals,
                qr_config=qr_config,
                cert_number_config=cert_num_config
            )

            stored_cert_url = minio_service.upload_bytes(
                bucket_name=settings.MINIO_BUCKET_CERTIFICATES,
                object_name=f"certs/{event.id}/{claim_code}.png",
                data=rendered_bytes,
                content_type="image/png"
            )

            if not cert:
                cert = Certificate(
                    event_id=event.id,
                    participant_id=p.id,
                    certificate_number=cert_num,
                    claim_code=claim_code,
                    status="GENERATED",
                    image_url=stored_cert_url,
                    checksum_sha256=checksum,
                    download_count=0
                )
                db.add(cert)
            else:
                cert.certificate_number = cert_num
                cert.claim_code = claim_code
                cert.status = "GENERATED"
                cert.image_url = stored_cert_url
                cert.checksum_sha256 = checksum

            db.commit()
            print(f"Generated Demo Certificate -> Recipient: {p.name} | Claim Code: {claim_code}")

        print("\nDemo seed completed successfully!")

    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
