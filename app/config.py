"""
Application Configuration Settings
Loads settings from environment variables with URL-encoding for special characters.
"""

import os
from typing import List
from urllib.parse import quote_plus
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "SecureCertFlow"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    APP_SECRET_KEY: str = Field(default="dev-secret-key-change-in-production-32chars")
    APP_BASE_URL: str = "https://sertifikat.uinjakarta.id"

    # Security & JWT
    JWT_SECRET_KEY: str = Field(default="dev-jwt-secret-key-change-in-production-32chars")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Database
    POSTGRES_HOST: str = "10.88.0.7"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = "postgres"
    POSTGRES_SCHEMA: str = "certflow"
    POSTGRES_POOL_SIZE: int = 10
    POSTGRES_MAX_OVERFLOW: int = 20

    # MinIO / S3 Object Storage
    MINIO_ENDPOINT: str = "10.88.0.11:9000"
    MINIO_SECURE: bool = False
    MINIO_ACCESS_KEY: str = "admin"
    MINIO_SECRET_KEY: str = ""
    MINIO_BUCKET_TEMPLATES: str = "cert-templates"
    MINIO_BUCKET_CERTIFICATES: str = "cert-outputs"
    MINIO_BUCKET_SIGNATURES: str = "cert-signatures"

    # Apache Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = "10.88.0.7:9092"
    KAFKA_SECURITY_PROTOCOL: str = "SASL_PLAINTEXT"
    KAFKA_SASL_MECHANISM: str = "PLAIN"
    KAFKA_SASL_USERNAME: str = "admin"
    KAFKA_SASL_PASSWORD: str = ""
    KAFKA_TOPIC_CERT_GENERATION: str = "cert_generation_queue"
    KAFKA_CONSUMER_GROUP: str = "cert_generation_workers"

    # CI/CD Webhook
    WEBHOOK_SECRET: str = "change_me_webhook_secret"

    # CORS
    CORS_ORIGINS: List[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True
    )

    @property
    def database_url(self) -> str:
        """Constructs safe synchronous PostgreSQL connection URL with URL-encoded password"""
        safe_pass = quote_plus(self.POSTGRES_PASSWORD) if self.POSTGRES_PASSWORD else ""
        return (
            f"postgresql://{self.POSTGRES_USER}:{safe_pass}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def async_database_url(self) -> str:
        """Constructs safe asynchronous PostgreSQL connection URL with URL-encoded password"""
        safe_pass = quote_plus(self.POSTGRES_PASSWORD) if self.POSTGRES_PASSWORD else ""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{safe_pass}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def minio_clean_endpoint(self) -> str:
        """Removes http:// or https:// prefix if included in MINIO_ENDPOINT"""
        endpoint = self.MINIO_ENDPOINT.strip()
        if endpoint.startswith("http://"):
            return endpoint[7:]
        elif endpoint.startswith("https://"):
            return endpoint[8:]
        return endpoint


settings = Settings()
