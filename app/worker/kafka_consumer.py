"""
Kafka Background Consumer Worker
Processes queued certificate generation tasks asynchronously with load leveling.
"""

import json
import logging
import time
import traceback
from typing import Optional
from kafka import KafkaConsumer
from sqlalchemy.orm import Session
from app.config import settings
from app.database import SessionLocal
from app.models import Event, Template, Certificate, Batch, Participant
from app.services import minio_service, cert_generator

logger = logging.getLogger(__name__)


class CertificateConsumerWorker:
    def __init__(self):
        self.topic = settings.KAFKA_TOPIC_CERT_GENERATION
        self.group_id = settings.KAFKA_CONSUMER_GROUP
        self.consumer: Optional[KafkaConsumer] = None
        self.running = False

    def _init_consumer(self):
        """Initializes Kafka consumer with SASL_PLAINTEXT PLAIN authentication"""
        try:
            config = {
                "bootstrap_servers": settings.KAFKA_BOOTSTRAP_SERVERS.split(","),
                "group_id": self.group_id,
                "auto_offset_reset": "earliest",
                "enable_auto_commit": True,
                "value_deserializer": lambda m: json.loads(m.decode("utf-8")),
                "session_timeout_ms": 30000,
                "heartbeat_interval_ms": 10000,
                "max_poll_interval_ms": 300000,
            }

            if settings.KAFKA_SECURITY_PROTOCOL == "SASL_PLAINTEXT":
                config.update({
                    "security_protocol": "SASL_PLAINTEXT",
                    "sasl_mechanism": settings.KAFKA_SASL_MECHANISM,
                    "sasl_plain_username": settings.KAFKA_SASL_USERNAME,
                    "sasl_plain_password": settings.KAFKA_SASL_PASSWORD,
                })

            self.consumer = KafkaConsumer(self.topic, **config)
            logger.info("Kafka Consumer connected to topic '%s' in group '%s'", self.topic, self.group_id)
        except Exception as e:
            logger.error("Failed to connect Kafka Consumer: %s", e)
            self.consumer = None

    def process_certificate_job(self, db: Session, payload: dict) -> bool:
        """
        Executes rendering for a single certificate and updates database state.
        """
        cert_id = payload.get("certificate_id")
        event_id = payload.get("event_id")
        batch_id = payload.get("batch_id")
        claim_code = payload.get("claim_code")
        cert_number = payload.get("certificate_number")
        dynamic_values = payload.get("dynamic_values", {})

        logger.info("Processing certificate ID %s for claim code %s", cert_id, claim_code)

        # 1. Fetch certificate and event template
        cert = db.query(Certificate).filter(Certificate.id == cert_id).first()
        if not cert:
            logger.error("Certificate ID %s not found in DB", cert_id)
            return False

        template = db.query(Template).filter(Template.event_id == event_id).first()
        if not template:
            err = f"Template not found for event {event_id}"
            logger.error(err)
            cert.status = "FAILED"
            cert.error_message = err
            db.commit()
            return False

        try:
            # Mark certificate as PROCESSING
            cert.status = "PROCESSING"
            db.commit()

            # 2. Download template background image
            bg_key = template.background_image_url
            if "/" in bg_key:
                bucket, obj_name = bg_key.split("/", 1)
            else:
                bucket = settings.MINIO_BUCKET_TEMPLATES
                obj_name = bg_key
            
            bg_bytes = minio_service.download_bytes(bucket, obj_name)

            # 3. Download signature if configured
            sig_bytes = None
            sig_config = None
            if template.signature_image_url and template.signature_x is not None:
                try:
                    sig_key = template.signature_image_url
                    if "/" in sig_key:
                        s_bucket, s_obj = sig_key.split("/", 1)
                    else:
                        s_bucket = settings.MINIO_BUCKET_SIGNATURES
                        s_obj = sig_key
                    sig_bytes = minio_service.download_bytes(s_bucket, s_obj)
                    sig_config = {
                        "pos_x": template.signature_x,
                        "pos_y": template.signature_y,
                        "width": template.signature_width or 200,
                        "height": template.signature_height or 100,
                    }
                except Exception as sig_err:
                    logger.warning("Could not load signature: %s", sig_err)

            # 4. Configure QR Code and Auto-numbering
            qr_verify_url = f"{settings.APP_BASE_URL}/verify/{claim_code}"
            qr_config = {
                "url": qr_verify_url,
                "pos_x": template.qr_x,
                "pos_y": template.qr_y,
                "size": template.qr_size or 150,
            }

            cert_number_config = {
                "number": cert_number,
                "pos_x": template.cert_number_x,
                "pos_y": template.cert_number_y,
                "font_size": template.cert_number_font_size or 24,
                "color": template.cert_number_color or "#1E293B",
            }

            # 5. Extract fields config
            fields_config = [
                {
                    "field_key": f.field_key,
                    "label": f.label,
                    "pos_x": f.pos_x,
                    "pos_y": f.pos_y,
                    "font_family": f.font_family,
                    "font_size": f.font_size,
                    "font_color": f.font_color,
                    "text_align": f.text_align,
                    "max_width": f.max_width,
                }
                for f in template.fields
            ]

            # 6. Render Certificate Image and compute SHA-256
            image_bytes, checksum = cert_generator.render(
                template_bytes=bg_bytes,
                fields_config=fields_config,
                dynamic_values=dynamic_values,
                signature_bytes=sig_bytes,
                signature_config=sig_config,
                qr_config=qr_config,
                cert_number_config=cert_number_config,
            )

            # 7. Upload generated certificate to MinIO output bucket
            object_name = f"certs/{event_id}/{claim_code}.png"
            stored_url = minio_service.upload_bytes(
                bucket_name=settings.MINIO_BUCKET_CERTIFICATES,
                object_name=object_name,
                data=image_bytes,
                content_type="image/png"
            )

            # 8. Update DB Certificate status
            cert.status = "GENERATED"
            cert.image_url = stored_url
            cert.checksum_sha256 = checksum
            cert.error_message = None

            # 9. Update batch progress if part of bulk import
            if batch_id:
                batch = db.query(Batch).filter(Batch.id == batch_id).first()
                if batch:
                    batch.processed_records += 1
                    batch.success_records += 1
                    if batch.processed_records >= batch.total_records:
                        batch.status = "completed"

            db.commit()
            logger.info("Successfully generated certificate %s [Checksum: %s]", cert_number, checksum[:10])
            return True

        except Exception as e:
            db.rollback()
            err_msg = f"Generation error: {str(e)}\n{traceback.format_exc()}"
            logger.error(err_msg)
            
            try:
                cert.status = "FAILED"
                cert.error_message = str(e)
                if batch_id:
                    batch = db.query(Batch).filter(Batch.id == batch_id).first()
                    if batch:
                        batch.processed_records += 1
                        batch.failed_records += 1
                        batch.error_log.append({"cert_id": str(cert_id), "error": str(e)})
                        if batch.processed_records >= batch.total_records:
                            batch.status = "completed"
                db.commit()
            except Exception as inner_e:
                logger.error("Failed to commit failure status: %s", inner_e)

            return False

    def start_consuming(self, max_messages: Optional[int] = None):
        """Main listening loop for Kafka consumer"""
        self.running = True
        logger.info("Starting Kafka Consumer worker loop...")

        while self.running:
            if not self.consumer:
                self._init_consumer()
                if not self.consumer:
                    time.sleep(3)
                    continue

            try:
                message_count = 0
                for message in self.consumer:
                    if not self.running:
                        break

                    payload = message.value
                    db = SessionLocal()
                    try:
                        self.process_certificate_job(db, payload)
                    finally:
                        db.close()

                    message_count += 1
                    if max_messages and message_count >= max_messages:
                        break

            except Exception as e:
                logger.error("Consumer loop exception: %s. Reconnecting in 3s...", e)
                time.sleep(3)
                self.consumer = None

    def stop(self):
        """Stops the consumer loop safely"""
        self.running = False
        if self.consumer:
            self.consumer.close()
