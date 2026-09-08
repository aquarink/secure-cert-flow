"""
Email Service for Secure CertFlow
Handles transactional notification emails for attendance check-in and certificate claims.
Includes anti-spam compliance, MIME multipart/alternative (Plain + HTML), and proper RFC headers.
"""

import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from typing import Optional

from app.config import settings

logger = logging.getLogger("securecertflow.email")


class EmailService:
    def __init__(self):
        self.host = settings.SMTP_HOST
        self.port = settings.SMTP_PORT
        self.user = settings.SMTP_USER
        self.password = settings.SMTP_PASSWORD
        self.from_name = settings.SMTP_FROM_NAME
        self.from_email = settings.SMTP_FROM_EMAIL
        self.use_ssl = settings.SMTP_USE_SSL
        self.timeout = settings.SMTP_TIMEOUT
        self.base_url = settings.APP_BASE_URL.rstrip("/")

    def build_claim_email(
        self,
        to_email: str,
        full_name: str,
        event_name: str,
        claim_code: str,
        role: str,
        paper_title: Optional[str] = None
    ) -> MIMEMultipart:
        """
        Builds a MIME multipart/alternative email with clean Plain Text and modern responsive HTML.
        Strictly conforms to anti-spam best practices (headers, MIME ratio, unsubscription notice).
        """
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Your Certificate Claim Code for {event_name} - Secure CertFlow"
        msg["From"] = f"{self.from_name} <{self.from_email}>"
        msg["To"] = to_email
        msg["Reply-To"] = self.from_email
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain="uinjakarta.id")
        msg["X-Mailer"] = "SecureCertFlow/1.0"

        verify_url = f"{self.base_url}/verify/{claim_code}"
        claim_portal_url = f"{self.base_url}/claim"

        paper_text_snippet = f"\nPaper: {paper_title}" if paper_title else ""
        paper_html_snippet = f"""
        <div style="margin: 6px 0; font-size: 13px; color: #475569;">
          <strong>Paper:</strong> <span style="color: #1e293b;">{paper_title}</span>
        </div>
        """ if paper_title else ""

        # 1. Plain Text Version (Vital for SpamAssassin score)
        text_body = f"""Dear {full_name},

Thank you for your verified attendance at {event_name} through the Secure CertFlow portal.

Your attendance details:
- Name: {full_name}
- Role: {role}{paper_text_snippet}
- Verification Status: Confirmed

Your Certificate Claim Code:
--------------------------------------------------
{claim_code}
--------------------------------------------------

Direct Certificate Link:
{verify_url}

How to Claim and Download Your Certificate:
1. Visit {claim_portal_url} or click the direct link above.
2. Enter your Claim Code: {claim_code}
3. Review your verified credentials and download your cryptographically signed PDF certificate.

If you have any questions, please contact the organizing committee.

Best regards,
{self.from_name} Team
UIN Syarif Hidayatullah Jakarta
{self.base_url}

---
You received this notification because your email ({to_email}) was submitted during check-in for {event_name}.
"""

        # 2. Modern Responsive HTML Version
        html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Certificate Claim Code - {claim_code}</title>
</head>
<body style="margin:0;padding:0;background-color:#f8fafc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#1e293b;-webkit-font-smoothing:antialiased;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#f8fafc;padding:32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:600px;background-color:#ffffff;border-radius:18px;box-shadow:0 4px 24px rgba(0,0,0,0.06);overflow:hidden;border:1px solid #e2e8f0;">
          
          <!-- Header Banner -->
          <tr>
            <td style="background:linear-gradient(135deg, #312e81 0%, #4338ca 50%, #4f46e5 100%);padding:36px 32px;text-align:center;">
              <div style="display:inline-block;padding:6px 14px;background:rgba(255,255,255,0.18);border-radius:20px;color:#ffffff;font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;margin-bottom:12px;">
                UIN Syarif Hidayatullah Jakarta
              </div>
              <h1 style="margin:0;color:#ffffff;font-size:22px;font-weight:800;line-height:1.35;letter-spacing:-0.3px;">
                Attendance Verified &amp; Certificate Issued
              </h1>
              <p style="margin:8px 0 0 0;color:#e0e7ff;font-size:13px;">
                {event_name}
              </p>
            </td>
          </tr>

          <!-- Main Content -->
          <tr>
            <td style="padding:36px 32px;">
              <p style="margin:0 0 16px 0;font-size:15px;line-height:1.6;color:#1e293b;">
                Dear <strong>{full_name}</strong>,
              </p>
              <p style="margin:0 0 20px 0;font-size:14px;line-height:1.6;color:#475569;">
                Thank you for your participation. Your attendance has been officially confirmed and cryptographically logged. Below is your unique Certificate Claim Code:
              </p>

              <!-- Attendance Summary Box -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#f1f5f9;border-radius:12px;margin:0 0 24px 0;">
                <tr>
                  <td style="padding:16px 20px;">
                    <div style="font-size:13px;color:#475569;margin-bottom:4px;">
                      <strong>Role:</strong> <span style="display:inline-block;padding:2px 8px;background:#e0e7ff;color:#3730a3;border-radius:6px;font-size:11px;font-weight:700;">{role}</span>
                    </div>
                    {paper_html_snippet}
                  </td>
                </tr>
              </table>

              <!-- Big Claim Code Card -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:linear-gradient(180deg, #fbfbfe 0%, #f5f3ff 100%);border:2px dashed #6366f1;border-radius:14px;margin:24px 0;text-align:center;">
                <tr>
                  <td style="padding:26px 20px;">
                    <div style="font-size:11px;font-weight:700;color:#4f46e5;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:8px;">
                      Certificate Claim Code
                    </div>
                    <div style="font-family:'Courier New',Courier,monospace;font-size:32px;font-weight:800;letter-spacing:6px;color:#1e1b4b;padding:4px 0;">
                      {claim_code}
                    </div>
                    <div style="font-size:12px;color:#64748b;margin-top:8px;">
                      Use this code to retrieve, verify, or download your official certificate.
                    </div>
                  </td>
                </tr>
              </table>

              <!-- Action Button CTA -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:28px 0 24px 0;">
                <tr>
                  <td align="center">
                    <a href="{verify_url}" target="_blank" style="display:inline-block;background:#4f46e5;color:#ffffff;text-decoration:none;font-size:15px;font-weight:700;padding:14px 32px;border-radius:10px;box-shadow:0 4px 14px rgba(79,70,229,0.35);letter-spacing:0.3px;">
                      Claim &amp; Download Certificate &rarr;
                    </a>
                  </td>
                </tr>
              </table>

              <!-- Step-by-Step Instructions -->
              <div style="background-color:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:20px;margin-top:28px;">
                <div style="font-size:13px;font-weight:700;color:#0f172a;margin-bottom:10px;">
                  Quick Instructions:
                </div>
                <ol style="margin:0;padding-left:20px;font-size:13px;line-height:1.75;color:#475569;">
                  <li>Click the claim button above or open <a href="{claim_portal_url}" style="color:#4f46e5;text-decoration:underline;">sertifikat.uinjakarta.id/claim</a> in your browser.</li>
                  <li>Enter your Claim Code: <strong style="font-family:monospace;color:#1e293b;">{claim_code}</strong></li>
                  <li>Preview your verified certificate details and click <strong>Unduh Sertifikat (PDF)</strong>.</li>
                </ol>
              </div>

              <p style="margin:24px 0 0 0;font-size:12px;line-height:1.6;color:#64748b;">
                <em>Note: Your certificate is generated dynamically from the latest verified records and signed cryptographically to prevent counterfeiting.</em>
              </p>

            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color:#f8fafc;padding:24px 32px;border-top:1px solid #e2e8f0;text-align:center;font-size:12px;color:#64748b;line-height:1.6;">
              <p style="margin:0 0 6px 0;font-weight:700;color:#334155;">
                Secure CertFlow &bull; UIN Syarif Hidayatullah Jakarta
              </p>
              <p style="margin:0 0 10px 0;font-size:11px;color:#64748b;">
                Cryptographically Secured &amp; Verifiable Credential Platform
              </p>
              <p style="margin:0;font-size:11px;color:#94a3b8;">
                You received this email because you checked in at {event_name}. If you did not participate, please contact the event committee.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        return msg

    def send_attendance_claim_email(
        self,
        to_email: str,
        full_name: str,
        event_name: str,
        claim_code: str,
        role: str,
        paper_title: Optional[str] = None
    ) -> bool:
        """
        Sends the claim code email synchronously or in a FastAPI background task.
        Safely catches network/SMTP exceptions without interrupting the caller.
        """
        if not settings.SMTP_ENABLED:
            logger.info("SMTP sending is disabled in settings. Skipping email dispatch.")
            return False

        if not to_email or not to_email.strip() or "@" not in to_email:
            logger.warning(f"Invalid email address '{to_email}'. Skipping email dispatch.")
            return False

        try:
            msg = self.build_claim_email(
                to_email=to_email.strip(),
                full_name=full_name.strip(),
                event_name=event_name.strip(),
                claim_code=claim_code.strip(),
                role=role.strip(),
                paper_title=paper_title.strip() if paper_title else None
            )

            logger.info(f"Connecting to SMTP {self.host}:{self.port} (SSL={self.use_ssl})...")

            if self.use_ssl or self.port == 465:
                ssl_ctx = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.host, self.port, context=ssl_ctx, timeout=self.timeout) as server:
                    if self.user and self.password:
                        server.login(self.user, self.password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as server:
                    server.ehlo()
                    ssl_ctx = ssl.create_default_context()
                    server.starttls(context=ssl_ctx)
                    server.ehlo()
                    if self.user and self.password:
                        server.login(self.user, self.password)
                    server.send_message(msg)

            logger.info(f"Claim code email successfully sent to {to_email} (Claim Code: {claim_code})")
            return True

        except smtplib.SMTPRecipientsRefused as e:
            logger.error(f"SMTP recipient refused for {to_email}: {e}")
            return False
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed for user {self.user}: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to send claim code email to {to_email}: {type(e).__name__} - {e}")
            return False


email_service = EmailService()
