-- =============================================================================
-- SECURE CERT FLOW - DATABASE INITIALIZATION SCHEMA
-- Database: PostgreSQL 14+
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. Users Table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    is_verified BOOLEAN DEFAULT FALSE NOT NULL,
    verification_token VARCHAR(255) NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- 2. Events Table
CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    location VARCHAR(255) NOT NULL,
    event_date DATE NOT NULL,
    description TEXT NULL,
    status VARCHAR(50) DEFAULT 'draft' NOT NULL, -- draft, published, archived
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_user_id ON events(user_id);
CREATE INDEX IF NOT EXISTS idx_events_event_date ON events(event_date);

-- 3. Templates Table
CREATE TABLE IF NOT EXISTS templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID UNIQUE NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    background_image_url VARCHAR(1024) NOT NULL,
    width INTEGER DEFAULT 1920 NOT NULL,
    height INTEGER DEFAULT 1080 NOT NULL,
    signature_image_url VARCHAR(1024) NULL,
    signature_x INTEGER NULL,
    signature_y INTEGER NULL,
    signature_width INTEGER NULL,
    signature_height INTEGER NULL,
    qr_x INTEGER NULL,
    qr_y INTEGER NULL,
    qr_size INTEGER DEFAULT 150 NOT NULL,
    qr_base_url VARCHAR(500) DEFAULT '/claim/' NOT NULL,
    cert_number_prefix VARCHAR(50) DEFAULT 'CERT' NOT NULL,
    cert_number_x INTEGER NULL,
    cert_number_y INTEGER NULL,
    cert_number_font_size INTEGER DEFAULT 24 NOT NULL,
    cert_number_color VARCHAR(20) DEFAULT '#1E293B' NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_templates_event_id ON templates(event_id);

-- 4. Template Fields (Dynamic Coordinate Placeholders)
CREATE TABLE IF NOT EXISTS template_fields (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
    field_key VARCHAR(100) NOT NULL, -- e.g. nama, judul_paper, peran
    label VARCHAR(100) NOT NULL,
    pos_x INTEGER NOT NULL,
    pos_y INTEGER NOT NULL,
    font_family VARCHAR(100) DEFAULT 'DejaVuSans-Bold.ttf' NOT NULL,
    font_size INTEGER DEFAULT 36 NOT NULL,
    font_color VARCHAR(20) DEFAULT '#1E293B' NOT NULL,
    text_align VARCHAR(20) DEFAULT 'center' NOT NULL, -- left, center, right
    max_width INTEGER NULL,
    is_required BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_template_fields_template_id ON template_fields(template_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_template_fields_uniq ON template_fields(template_id, field_key);

-- 5. Batches Table (Bulk Import Processing)
CREATE TABLE IF NOT EXISTS batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    total_records INTEGER DEFAULT 0 NOT NULL,
    processed_records INTEGER DEFAULT 0 NOT NULL,
    success_records INTEGER DEFAULT 0 NOT NULL,
    failed_records INTEGER DEFAULT 0 NOT NULL,
    status VARCHAR(50) DEFAULT 'pending' NOT NULL, -- pending, processing, completed, failed
    error_log JSONB DEFAULT '[]'::jsonb NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_batches_event_id ON batches(event_id);
CREATE INDEX IF NOT EXISTS idx_batches_status ON batches(status);

-- 6. Participants Table
CREATE TABLE IF NOT EXISTS participants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    batch_id UUID NULL REFERENCES batches(id) ON DELETE SET NULL,
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    role VARCHAR(100) NOT NULL, -- Author, Presenter, Attendee, Committee, etc.
    paper_title TEXT NULL,
    custom_data JSONB DEFAULT '{}'::jsonb NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_participants_event_id ON participants(event_id);
CREATE INDEX IF NOT EXISTS idx_participants_batch_id ON participants(batch_id);
CREATE INDEX IF NOT EXISTS idx_participants_email ON participants(email);

-- 7. Certificates Table
CREATE TABLE IF NOT EXISTS certificates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    participant_id UUID NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
    batch_id UUID NULL REFERENCES batches(id) ON DELETE SET NULL,
    certificate_number VARCHAR(100) UNIQUE NOT NULL,
    claim_code VARCHAR(16) UNIQUE NOT NULL,
    pdf_url VARCHAR(1024) NULL,
    image_url VARCHAR(1024) NULL,
    checksum_sha256 VARCHAR(64) NULL,
    status VARCHAR(50) DEFAULT 'PENDING' NOT NULL, -- PENDING, PROCESSING, GENERATED, FAILED, CLAIMED
    error_message TEXT NULL,
    claimed_at TIMESTAMPTZ NULL,
    download_count INTEGER DEFAULT 0 NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_certificates_event_id ON certificates(event_id);
CREATE INDEX IF NOT EXISTS idx_certificates_participant_id ON certificates(participant_id);
CREATE INDEX IF NOT EXISTS idx_certificates_claim_code ON certificates(claim_code);
CREATE INDEX IF NOT EXISTS idx_certificates_number ON certificates(certificate_number);
CREATE INDEX IF NOT EXISTS idx_certificates_status ON certificates(status);

-- 8. Webhook Logs Table (CI/CD and external event integration)
CREATE TABLE IF NOT EXISTS webhook_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(50) NOT NULL,
    response_message TEXT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_webhook_logs_event_type ON webhook_logs(event_type);
