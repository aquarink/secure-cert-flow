"""
MinIO / S3 Object Storage Service
Handles secure file storage for certificate templates, signatures, and generated output.
Includes short connection timeouts and resilient local fallback.
"""

import io
import os
import urllib3
import logging
from typing import Optional
from datetime import timedelta
from minio import Minio
from app.config import settings

logger = logging.getLogger(__name__)

# Local fallback directory for offline development or storage caching
LOCAL_STORAGE_DIR = "/var/www/sertifikat/storage"
os.makedirs(LOCAL_STORAGE_DIR, exist_ok=True)


class MinIOService:
    def __init__(self):
        self.endpoint = settings.minio_clean_endpoint
        self.access_key = settings.MINIO_ACCESS_KEY
        self.secret_key = settings.MINIO_SECRET_KEY
        self.secure = settings.MINIO_SECURE
        self.client: Optional[Minio] = None
        self._init_client()

    def _init_client(self):
        """Initializes the MinIO SDK client instance with 2-second timeout"""
        try:
            # Custom HTTP client with 2.0s connect timeout to prevent startup hangs
            http_client = urllib3.PoolManager(
                timeout=urllib3.Timeout(connect=2.0, read=10.0),
                retries=urllib3.Retry(total=1, backoff_factor=0.2)
            )
            self.client = Minio(
                endpoint=self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure,
                http_client=http_client
            )
            logger.info(f"MinIO client initialized for endpoint {self.endpoint}")
        except Exception as e:
            logger.warning(f"MinIO initialization warning: {e}. Fallback storage active.")
            self.client = None

    def ensure_buckets(self):
        """Ensures all required buckets exist in MinIO (non-blocking fallback)"""
        if not self.client:
            return
        
        buckets = [
            settings.MINIO_BUCKET_TEMPLATES,
            settings.MINIO_BUCKET_CERTIFICATES,
            settings.MINIO_BUCKET_SIGNATURES,
        ]
        
        for bucket in buckets:
            try:
                if not self.client.bucket_exists(bucket):
                    self.client.make_bucket(bucket)
                    logger.info(f"Created MinIO bucket: {bucket}")
            except Exception as e:
                logger.warning(f"MinIO bucket check bypassed ({e}). Local storage available.")
                break  # Don't hang on consecutive bucket checks if host is offline

    def upload_bytes(
        self,
        bucket_name: str,
        object_name: str,
        data: bytes,
        content_type: str = "image/png"
    ) -> str:
        """
        Uploads in-memory byte buffer to MinIO bucket.
        Falls back to local file storage if MinIO is not reachable.
        """
        # Save local copy for resilience
        local_path = os.path.join(LOCAL_STORAGE_DIR, bucket_name, object_name)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(data)

        if self.client:
            try:
                data_stream = io.BytesIO(data)
                self.client.put_object(
                    bucket_name=bucket_name,
                    object_name=object_name,
                    data=data_stream,
                    length=len(data),
                    content_type=content_type
                )
                logger.info(f"Uploaded {object_name} to MinIO bucket {bucket_name}")
                return f"{bucket_name}/{object_name}"
            except Exception as e:
                logger.warning(f"MinIO put_object failed ({e}), stored in local cache.")
        
        return f"{bucket_name}/{object_name}"

    def download_bytes(self, bucket_name: str, object_name: str) -> bytes:
        """
        Downloads object bytes from MinIO or local fallback storage.
        """
        if self.client:
            try:
                response = self.client.get_object(bucket_name, object_name)
                data = response.read()
                response.close()
                response.release_conn()
                return data
            except Exception as e:
                logger.warning(f"MinIO download failed ({e}), checking local cache...")
        
        # Check local fallback cache
        local_path = os.path.join(LOCAL_STORAGE_DIR, bucket_name, object_name)
        if os.path.exists(local_path):
            with open(local_path, "rb") as f:
                return f.read()
        
        raise FileNotFoundError(f"Object {bucket_name}/{object_name} not found in MinIO or local storage.")

    def get_presigned_url(
        self,
        bucket_name: str,
        object_name: str,
        expires: timedelta = timedelta(hours=2)
    ) -> str:
        """
        Generates a secure presigned download/preview URL for participant access.
        """
        if self.client:
            try:
                return self.client.presigned_get_object(
                    bucket_name=bucket_name,
                    object_name=object_name,
                    expires=expires
                )
            except Exception as e:
                logger.warning(f"Presigned URL generation error: {e}")
        
        # Fallback local public route
        return f"/api/v1/storage/{bucket_name}/{object_name}"


# Global MinIO Service Singleton
minio_service = MinIOService()
