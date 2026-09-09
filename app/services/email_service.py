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
        paper_title: Optional[str] = None,
        header_title: Optional[str] = None,
        intro_text: Optional[str] = None,
        notice_reason: Optional[str] = None
    ) -> MIMEMultipart:
        """
        Builds a MIME multipart/alternative email with clean Plain Text and modern responsive HTML.
        Strictly conforms to anti-spam best practices (headers, MIME ratio, unsubscription notice).
        Dynamically adapts text for attendees, presenters, authors, and special roles (committee, reviewer, etc.).
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

        is_attendee_role = str(role).strip().lower() in ["participant", "peserta", "attendee", "presenter", "author", "pemakalah", "penulis"]
        effective_header = header_title or ("Attendance Verified & Certificate Issued" if is_attendee_role else f"Certificate Issued - {role}")
        effective_intro = intro_text or (
            "Thank you for your active participation. Your check-in and attendance have been officially confirmed and cryptographically logged. Below is your official Certificate Claim Code:"
            if is_attendee_role else
            f"Thank you for your valuable contribution and dedication as <strong style=\"color:#ffffff;\">{role}</strong> for {event_name}. Below is your official Certificate Claim Code:"
        )
        effective_plain_intro = (
            f"Thank you for your verified attendance at {event_name} through the Secure CertFlow portal."
            if is_attendee_role else
            f"Thank you for your valuable contribution and service as {role} at {event_name} through the Secure CertFlow portal."
        )
        effective_notice = notice_reason or f"You received this notification because your email ({to_email}) was registered for {event_name}."

        paper_text_snippet = f"\nPaper: {paper_title}" if paper_title else ""
        paper_html_snippet = f"""
        <div style="margin: 6px 0; font-size: 13px; color: #94a3b8;">
          <strong style="color:#cbd5e1;">Paper:</strong> <span style="color: #f1f5f9;">{paper_title}</span>
        </div>
        """ if paper_title else ""

        # 1. Plain Text Version (Vital for SpamAssassin score)
        text_body = f"""Dear {full_name},

{effective_plain_intro}

Your details:
- Name: {full_name}
- Role: {role}{paper_text_snippet}
- Verification Status: Confirmed & Issued

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
{effective_notice}
"""

        # 2. Modern Responsive HTML Version (100% Light & Dark Mode Proof)
        html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="color-scheme" content="light dark">
  <meta name="supported-color-schemes" content="light dark">
  <title>Certificate Claim Code - {claim_code}</title>
  <style>
    :root {{
      color-scheme: light dark;
      supported-color-schemes: light dark;
    }}
  </style>
</head>
<body bgcolor="#0b0f19" style="margin:0;padding:0;background-color:#0b0f19;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#e2e8f0;-webkit-font-smoothing:antialiased;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" bgcolor="#0b0f19" style="background-color:#0b0f19;padding:32px 16px;">
    <tr>
      <td align="center" bgcolor="#0b0f19">
        <table role="presentation" width="100%" max-width="600" cellspacing="0" cellpadding="0" border="0" bgcolor="#131b2e" style="max-width:600px;background-color:#131b2e;border-radius:18px;overflow:hidden;border:1px solid #1e293b;box-shadow:0 8px 30px rgba(0,0,0,0.5);">
          
          <!-- Header Banner -->
          <tr>
            <td bgcolor="#1e1b4b" style="background-color:#1e1b4b;padding:36px 32px;text-align:center;border-bottom:1px solid #312e81;">
              <div style="display:inline-block;padding:6px 14px;background-color:#312e81;border:1px solid #4338ca;border-radius:20px;color:#c7d2fe;font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;margin-bottom:12px;">
                UIN Syarif Hidayatullah Jakarta
              </div>
              <h1 style="margin:0;color:#ffffff;font-size:22px;font-weight:800;line-height:1.35;letter-spacing:-0.3px;">
                {effective_header}
              </h1>
              <p style="margin:8px 0 0 0;color:#a5b4fc;font-size:13px;font-weight:500;">
                {event_name}
              </p>
            </td>
          </tr>

          <!-- Main Content -->
          <tr>
            <td bgcolor="#131b2e" style="padding:36px 32px;background-color:#131b2e;">
              <p style="margin:0 0 16px 0;font-size:15px;line-height:1.6;color:#f8fafc;">
                Dear <strong style="color:#ffffff;">{full_name}</strong>,
              </p>
              <p style="margin:0 0 20px 0;font-size:14px;line-height:1.6;color:#94a3b8;">
                {effective_intro}
              </p>

              <!-- Attendance Summary Box -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" bgcolor="#0b0f19" style="background-color:#0b0f19;border:1px solid #1e293b;border-radius:12px;margin:0 0 24px 0;">
                <tr>
                  <td bgcolor="#0b0f19" style="padding:16px 20px;">
                    <div style="font-size:13px;color:#94a3b8;margin-bottom:4px;">
                      <strong style="color:#cbd5e1;">Role:</strong> <span style="display:inline-block;padding:2px 10px;background-color:#1e1b4b;border:1px solid #4338ca;color:#c7d2fe;border-radius:6px;font-size:11px;font-weight:700;">{role}</span>
                    </div>
                    {paper_html_snippet}
                  </td>
                </tr>
              </table>

              <!-- Big Claim Code Card (High Contrast Dark Slate + Vivid Amber Gold) -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" bgcolor="#070a12" style="background-color:#070a12;border:2px dashed #4f46e5;border-radius:14px;margin:24px 0;text-align:center;">
                <tr>
                  <td bgcolor="#070a12" style="padding:26px 20px;text-align:center;">
                    <div style="font-size:11px;font-weight:700;color:#818cf8;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:10px;">
                      Your Certificate Claim Code
                    </div>
                    
                    <table role="presentation" cellspacing="0" cellpadding="0" border="0" align="center" style="margin:0 auto;">
                      <tr>
                        <td bgcolor="#1e1b4b" style="background-color:#1e1b4b;border:2px solid #4f46e5;border-radius:12px;padding:12px 28px;text-align:center;">
                          <span style="font-family:'Courier New',Courier,monospace;font-size:34px;font-weight:900;letter-spacing:6px;color:#fbbf24 !important;display:inline-block;line-height:1;">
                            {claim_code}
                          </span>
                        </td>
                      </tr>
                    </table>

                    <div style="font-size:12px;color:#94a3b8;margin-top:12px;">
                      Keep this 8-character code safe to retrieve or download your certificate anytime.
                    </div>
                  </td>
                </tr>
              </table>

              <!-- Action Button CTA -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:28px 0 24px 0;">
                <tr>
                  <td align="center">
                    <a href="{verify_url}" target="_blank" style="display:inline-block;background-color:#4f46e5;color:#ffffff !important;text-decoration:none;font-size:15px;font-weight:700;padding:14px 34px;border-radius:10px;box-shadow:0 4px 16px rgba(79,70,229,0.5);letter-spacing:0.3px;">
                      Claim &amp; Download Certificate &rarr;
                    </a>
                  </td>
                </tr>
              </table>

              <!-- Step-by-Step Instructions -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" bgcolor="#0b0f19" style="background-color:#0b0f19;border:1px solid #1e293b;border-radius:12px;margin-top:28px;">
                <tr>
                  <td bgcolor="#0b0f19" style="padding:20px;">
                    <div style="font-size:13px;font-weight:700;color:#f8fafc;margin-bottom:10px;">
                      How to Access Your Certificate:
                    </div>
                    <ol style="margin:0;padding-left:20px;font-size:13px;line-height:1.75;color:#94a3b8;">
                      <li>Click the button above or visit <a href="{claim_portal_url}" style="color:#818cf8;text-decoration:underline;">sertifikat.uinjakarta.id/claim</a></li>
                      <li>Enter your Claim Code: <strong style="font-family:monospace;color:#fbbf24;background-color:#1e1b4b;padding:2px 6px;border-radius:4px;">{claim_code}</strong></li>
                      <li>Preview your verified certificate details and click <strong style="color:#e2e8f0;">Unduh Sertifikat (PDF)</strong>.</li>
                    </ol>
                  </td>
                </tr>
              </table>

              <p style="margin:24px 0 0 0;font-size:12px;line-height:1.6;color:#64748b;">
                <em>Note: Your certificate is generated dynamically from the latest verified records and signed cryptographically to prevent counterfeiting.</em>
              </p>

            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td bgcolor="#0b0f19" style="background-color:#0b0f19;padding:24px 32px;border-top:1px solid #1e293b;text-align:center;font-size:12px;color:#64748b;line-height:1.6;">
              <p style="margin:0 0 6px 0;font-weight:700;color:#94a3b8;">
                Secure CertFlow &bull; UIN Syarif Hidayatullah Jakarta
              </p>
              <p style="margin:0 0 10px 0;font-size:11px;color:#64748b;">
                Cryptographically Secured &amp; Verifiable Credential Platform
              </p>
              <p style="margin:0;font-size:11px;color:#475569;">
                {effective_notice}
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
        paper_title: Optional[str] = None,
        header_title: Optional[str] = None,
        intro_text: Optional[str] = None,
        notice_reason: Optional[str] = None
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
                paper_title=paper_title.strip() if paper_title else None,
                header_title=header_title,
                intro_text=intro_text,
                notice_reason=notice_reason
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

    def send_special_role_claim_email(
        self,
        to_email: str,
        full_name: str,
        event_name: str,
        claim_code: str,
        role: str
    ) -> bool:
        """
        Convenience wrapper specifically for special roles (Committee, Reviewer, Cleaning Service, etc.)
        """
        return self.send_attendance_claim_email(
            to_email=to_email,
            full_name=full_name,
            event_name=event_name,
            claim_code=claim_code,
            role=role,
            header_title=f"Official Certificate - {role}",
            intro_text=f"Thank you for your valuable contribution and dedication as <strong style=\"color:#ffffff;\">{role}</strong> for {event_name}. Below is your official Certificate Claim Code:",
            notice_reason=f"You received this notification because you were issued an official certificate as {role} for {event_name}."
        )


email_service = EmailService()
