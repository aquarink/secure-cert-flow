"""
CI/CD Webhook Endpoint
Handles automated GitHub deployments with HMAC-SHA256 signature verification.
"""

import hmac
import hashlib
import json
import logging
import subprocess
from fastapi import APIRouter, Request, Header, HTTPException, status, BackgroundTasks, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.webhook import WebhookLog
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["CI/CD Webhooks"])


def execute_deployment_script():
    """Runs deployment script asynchronously after webhook validation"""
    script_path = "/var/www/sertifikat/scripts/deploy_webhook.sh"
    try:
        res = subprocess.run(
            ["bash", script_path],
            capture_output=True,
            text=True,
            timeout=300
        )
        logger.info(f"Deployment script output: {res.stdout}")
        if res.returncode != 0:
            logger.error(f"Deployment script error: {res.stderr}")
    except Exception as e:
        logger.error(f"Deployment script execution failed: {str(e)}")


@router.post("/github", status_code=status.HTTP_200_OK)
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: str = Header("push"),
    x_hub_signature_256: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    GitHub CI/CD Webhook Receiver.
    Validates HMAC signature, records audit log, and triggers deployment.
    """
    raw_body = await request.body()
    
    # 1. Verify HMAC Signature if secret is configured
    if settings.WEBHOOK_SECRET and settings.WEBHOOK_SECRET != "change_me_webhook_secret":
        if not x_hub_signature_256:
            raise HTTPException(status_code=400, detail="Missing X-Hub-Signature-256 header")
        
        expected_sig = "sha256=" + hmac.new(
            settings.WEBHOOK_SECRET.encode("utf-8"),
            raw_body,
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected_sig, x_hub_signature_256):
            raise HTTPException(status_code=403, detail="Invalid webhook signature")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        payload = {"raw": raw_body.decode("utf-8", errors="ignore")}

    # 2. Check if pushed to main branch
    ref = payload.get("ref", "")
    is_main_branch = ref == "refs/heads/main"

    webhook_log = WebhookLog(
        event_type=x_github_event,
        payload=payload,
        status="triggered" if is_main_branch else "ignored",
        response_message="Deployment triggered for main branch" if is_main_branch else f"Ignored ref: {ref}"
    )
    db.add(webhook_log)
    db.commit()

    # 3. Schedule deployment task
    if is_main_branch:
        background_tasks.add_task(execute_deployment_script)
        return {"status": "success", "message": "Deployment initiated for main branch."}

    return {"status": "ignored", "message": f"Push on branch {ref} ignored."}
