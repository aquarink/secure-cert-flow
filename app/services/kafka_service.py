"""
Apache Kafka Producer Service
Dispatches asynchronous certificate generation jobs to the message broker.
"""

import json
import logging
from typing import Dict, Any, Optional
from kafka import KafkaProducer
from app.config import settings

logger = logging.getLogger(__name__)


class KafkaService:
    def __init__(self):
        self.producer: Optional[KafkaProducer] = None
        self._init_producer()

    def _init_producer(self):
        """Initializes KafkaProducer with SASL_PLAINTEXT and PLAIN credentials"""
        try:
            config = {
                "bootstrap_servers": settings.KAFKA_BOOTSTRAP_SERVERS.split(","),
                "value_serializer": lambda v: json.dumps(v).encode("utf-8"),
                "request_timeout_ms": 10000,
                "retries": 3,
            }

            if settings.KAFKA_SECURITY_PROTOCOL == "SASL_PLAINTEXT":
                config.update({
                    "security_protocol": "SASL_PLAINTEXT",
                    "sasl_mechanism": settings.KAFKA_SASL_MECHANISM,
                    "sasl_plain_username": settings.KAFKA_SASL_USERNAME,
                    "sasl_plain_password": settings.KAFKA_SASL_PASSWORD,
                })

            self.producer = KafkaProducer(**config)
            logger.info("Kafka Producer connected successfully to %s", settings.KAFKA_BOOTSTRAP_SERVERS)
        except Exception as e:
            logger.error("Failed to initialize Kafka Producer: %s", e)
            self.producer = None

    def send_certificate_job(self, message: Dict[str, Any], topic: Optional[str] = None) -> bool:
        """
        Sends a certificate generation job payload to Kafka topic.
        Message payload structure:
        {
            "certificate_id": str,
            "participant_id": str,
            "event_id": str,
            "batch_id": Optional[str],
            "claim_code": str,
            "certificate_number": str,
            "dynamic_values": dict,
            "timestamp": str
        }
        """
        target_topic = topic or settings.KAFKA_TOPIC_CERT_GENERATION
        
        if not self.producer:
            self._init_producer()

        if self.producer:
            try:
                future = self.producer.send(target_topic, value=message)
                record_metadata = future.get(timeout=10)
                logger.info(
                    "Enqueued cert job to Kafka topic %s [partition %s, offset %s]",
                    record_metadata.topic,
                    record_metadata.partition,
                    record_metadata.offset,
                )
                return True
            except Exception as e:
                logger.error("Error sending message to Kafka: %s", e)
                return False
        else:
            logger.warning("Kafka Producer unavailable, job could not be enqueued to broker.")
            return False

    def close(self):
        """Flushes and closes producer connection"""
        if self.producer:
            self.producer.flush()
            self.producer.close()


# Global Kafka Service Singleton
kafka_service = KafkaService()
