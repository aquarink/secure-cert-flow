#!/usr/bin/env bash
# ==============================================================================
# SECURE CERT FLOW - CI/CD AUTOMATED DEPLOYMENT SCRIPT
# Triggered by GitHub Webhook on push to main branch
# ==============================================================================

set -e

PROJECT_DIR="/var/www/sertifikat"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"
VENV_PIP="$PROJECT_DIR/.venv/bin/pip"
LOG_FILE="$PROJECT_DIR/deploy.log"

echo "========================================================" >> "$LOG_FILE"
echo "Deployment started at $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"

cd "$PROJECT_DIR"

# 1. Fetch latest changes from GitHub
echo "[1/4] Pulling latest changes from Git repository..." >> "$LOG_FILE"
git fetch origin main >> "$LOG_FILE" 2>&1
git reset --hard origin/main >> "$LOG_FILE" 2>&1

# 2. Update Python dependencies
echo "[2/4] Updating dependencies..." >> "$LOG_FILE"
if [ -f "$PROJECT_DIR/.venv/bin/activate" ]; then
    "$VENV_PIP" install -r "$PROJECT_DIR/requirements.txt" >> "$LOG_FILE" 2>&1
fi

# 3. Apply database migrations
echo "[3/4] Syncing database schema..." >> "$LOG_FILE"
"$VENV_PYTHON" -c "
from app.database import engine, Base
from app.models import *
Base.metadata.create_all(bind=engine)
print('Schema successfully synchronized!')
" >> "$LOG_FILE" 2>&1

# 4. Restart Services (Systemd or PM2 or Process Reload)
echo "[4/4] Reloading application processes..." >> "$LOG_FILE"
if systemctl is-active --quiet certflow-api; then
    sudo systemctl restart certflow-api
    sudo systemctl restart certflow-worker
    echo "Systemd services restarted." >> "$LOG_FILE"
else
    echo "Process restart signal sent." >> "$LOG_FILE"
fi

echo "Deployment finished successfully at $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
echo "========================================================" >> "$LOG_FILE"
