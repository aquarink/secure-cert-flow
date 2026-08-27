#!/usr/bin/env python3
"""
Secure Cert Flow - Background Kafka Consumer Runner
Starts the standalone background worker for consuming certificate rendering jobs.

Usage:
    python scripts/run_worker.py
"""

import sys
import os
import signal
import logging

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.worker.kafka_consumer import CertificateConsumerWorker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [Worker] %(message)s"
)
logger = logging.getLogger("worker_runner")


def main():
    logger.info("Starting Secure Cert Flow - Kafka Consumer Worker...")
    worker = CertificateConsumerWorker()

    def handle_signal(sig, frame):
        logger.info("Termination signal received. Gracefully shutting down worker...")
        worker.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        worker.start_consuming()
    except Exception as e:
        logger.error(f"Worker encountered fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
