"""Outgoing email: SMTP delivery, development outbox and code email templates."""
import datetime
import html
import html.parser
import os
import secrets
import sqlite3
import sys
import threading
from typing import Any, Dict, List, Optional, Tuple


def render_code_email(heading: str, intro: str, code: str, outro: str) -> Tuple[str, str]:
    """Builds the plain-text and HTML bodies of a one-time code email."""
    text = f"{heading}\n\n{intro}\n\nКод: {code}\n\n{outro}\n\nSmartContractum\n"
    esc = html.escape
    html_body = f"""<!doctype html>
<html lang="ru"><body style="margin:0;padding:0;background:#f4f5f7;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f5f7;padding:32px 16px;font-family:Arial,Helvetica,sans-serif;">
<tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:480px;background:#ffffff;border:1px solid #e5e7eb;border-radius:12px;">
<tr><td style="padding:28px 32px 8px;font-size:18px;font-weight:bold;color:#2563eb;">SmartContractum</td></tr>
<tr><td style="padding:8px 32px 0;font-size:20px;font-weight:bold;color:#111827;">{esc(heading)}</td></tr>
<tr><td style="padding:12px 32px 0;font-size:15px;line-height:1.5;color:#4b5563;">{esc(intro)}</td></tr>
<tr><td style="padding:20px 32px;">
<div style="display:inline-block;padding:12px 20px;background:#eff6ff;border-radius:8px;font-size:30px;font-weight:bold;letter-spacing:6px;color:#111827;">{esc(code)}</div>
</td></tr>
<tr><td style="padding:0 32px 28px;font-size:13px;line-height:1.5;color:#6b7280;">{esc(outro)}</td></tr>
</table>
</td></tr>
</table>
</body></html>"""
    return text, html_body


def render_notice_email(heading: str, intro: str, details: str, button_text: str, button_url: str) -> Tuple[str, str]:
    """Builds the plain-text and HTML bodies of an informational email with one call to action."""
    text = f"{heading}\n\n{intro}\n\n" + (f"{details}\n\n" if details else "") + f"{button_text}: {button_url}\n\nSmartContractum\n"
    esc = html.escape
    details_html = (
        f'<tr><td style="padding:16px 32px 0;"><div style="padding:14px 16px;background:#f9fafb;border-left:3px solid #2563eb;'
        f'border-radius:6px;font-size:15px;line-height:1.55;color:#111827;white-space:pre-line;">{esc(details)}</div></td></tr>'
        if details else ""
    )
    html_body = f"""<!doctype html>
<html lang="ru"><body style="margin:0;padding:0;background:#f4f5f7;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f5f7;padding:32px 16px;font-family:Arial,Helvetica,sans-serif;">
<tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;background:#ffffff;border:1px solid #e5e7eb;border-radius:12px;">
<tr><td style="padding:28px 32px 8px;font-size:18px;font-weight:bold;color:#2563eb;">SmartContractum</td></tr>
<tr><td style="padding:8px 32px 0;font-size:20px;font-weight:bold;color:#111827;">{esc(heading)}</td></tr>
<tr><td style="padding:12px 32px 0;font-size:15px;line-height:1.55;color:#4b5563;">{esc(intro)}</td></tr>
{details_html}
<tr><td style="padding:24px 32px 28px;"><a href="{esc(button_url)}" style="display:inline-block;padding:11px 20px;background:#2563eb;border-radius:8px;color:#ffffff;font-size:15px;font-weight:bold;text-decoration:none;">{esc(button_text)}</a></td></tr>
</table>
</td></tr>
</table>
</body></html>"""
    return text, html_body


class EmailService:
    """Mail adapter: real SMTP when configured, otherwise an offline outbox for development."""

    def __init__(self):
        self.simulate_failure = False
        self.sent_emails: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    @staticmethod
    def settings() -> Dict[str, Any]:
        host = os.environ.get("SMTP_HOST", "").strip()
        port = int(os.environ.get("SMTP_PORT", "465").strip() or "465")
        user = os.environ.get("SMTP_USER", "").strip()
        return {
            "adapter": os.environ.get("MAIL_ADAPTER", "smtp" if host else "fake").strip().lower(),
            "host": host,
            "port": port,
            "user": user,
            "password": os.environ.get("SMTP_PASSWORD", ""),
            "use_ssl": os.environ.get("SMTP_USE_SSL", "1" if port == 465 else "0").strip().lower() in ("1", "true", "yes"),
            "use_tls": os.environ.get("SMTP_USE_TLS", "1").strip().lower() in ("1", "true", "yes"),
            "from_email": os.environ.get("SMTP_FROM_EMAIL", "").strip() or user,
            "from_name": os.environ.get("SMTP_FROM_NAME", "SmartContractum").strip(),
        }

    def is_configured(self) -> bool:
        s = self.settings()
        return bool(s["host"]) and bool(s["from_email"]) and s["adapter"] != "fake"

    def describe(self) -> str:
        s = self.settings()
        if not self.is_configured():
            return "Mail: development outbox only (no SMTP_HOST); codes are stored in the email_outbox table, nothing is delivered"
        mode = "SSL" if s["use_ssl"] else ("STARTTLS" if s["use_tls"] else "plain")
        return f"Mail: SMTP {s['host']}:{s['port']} ({mode}) as {s['from_email'] or '<no sender>'}"

    def set_simulate_failure(self, fail: bool) -> None:
        self.simulate_failure = fail

    def clear_sent_emails(self) -> None:
        with self._lock:
            self.sent_emails.clear()

    def get_sent_emails(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self.sent_emails)

    def send_verification_email(
        self,
        conn: sqlite3.Connection,
        recipient: str,
        code: str,
        login: str
    ) -> Tuple[bool, Optional[str]]:
        body_text, html_body = render_code_email(
            "Подтвердите email",
            f"Здравствуйте, {login}! Чтобы завершить регистрацию на SmartContractum, введите этот код в окне регистрации.",
            code,
            "Код действует 10 минут. Если вы не регистрировались, просто проигнорируйте это письмо."
        )
        return self.send_email(
            conn, recipient, "Код подтверждения регистрации SmartContractum", body_text,
            extra={"code": code, "login": login}, html_body=html_body
        )

    def deliver_smtp(self, recipient: str, subject: str, body_text: str, html_body: Optional[str] = None) -> None:
        """Sends one message through the configured SMTP server; raises on any failure."""
        import email.utils
        import smtplib
        import ssl
        from email.message import EmailMessage

        s = self.settings()
        if not s["from_email"]:
            raise RuntimeError("SMTP_FROM_EMAIL or SMTP_USER must be set")
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = email.utils.formataddr((s["from_name"], s["from_email"]))
        msg["To"] = recipient
        msg["Date"] = email.utils.formatdate(localtime=False)
        msg["Message-ID"] = email.utils.make_msgid(domain=s["from_email"].split("@")[-1])
        msg.set_content(body_text)
        if html_body:
            msg.add_alternative(html_body, subtype="html")

        context = ssl.create_default_context()
        if s["use_ssl"]:
            smtp = smtplib.SMTP_SSL(s["host"], s["port"], timeout=15, context=context)
        else:
            smtp = smtplib.SMTP(s["host"], s["port"], timeout=15)
        try:
            if not s["use_ssl"] and s["use_tls"]:
                smtp.starttls(context=context)
            if s["user"] and s["password"]:
                smtp.login(s["user"], s["password"])
            smtp.send_message(msg)
        finally:
            try:
                smtp.quit()
            except Exception:
                pass

    def send_email(
        self,
        conn: sqlite3.Connection,
        recipient: str,
        subject: str,
        body_text: str,
        extra: Optional[Dict[str, Any]] = None,
        html_body: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """Delivers one message via SMTP (or the development outbox) and records it in email_outbox."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        outbox_id = f"outbox_{secrets.token_hex(16)}"
        stored_body = body_text

        def record_outbox(status: str, error_message: Optional[str]) -> None:
            sent_at = now_iso if status == "sent" else None
            with conn:
                conn.execute("""
                    INSERT INTO email_outbox (id, recipient, subject, body_text, status, error_message, created_at, sent_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (outbox_id, recipient, subject, stored_body, status, error_message, now_iso, sent_at))

        if self.simulate_failure or os.environ.get("FAIL_MAIL_DELIVERY") == "1":
            err_msg = "Ошибка отправки письма: Simulated SMTP delivery failure"
            try:
                record_outbox("failed", err_msg)
            except Exception:
                pass
            return False, err_msg

        if self.is_configured():
            # Delivered codes are not kept in clear text in the database
            code = (extra or {}).get("code")
            if code:
                stored_body = body_text.replace(code, "******")
            try:
                self.deliver_smtp(recipient, subject, body_text, html_body)
            except Exception as e:
                sys.stderr.write(f"[mail] delivery to {recipient} failed: {e}\n")
                try:
                    record_outbox("failed", f"SMTP error: {type(e).__name__}")
                except Exception:
                    pass
                return False, "Не удалось отправить письмо. Попробуйте позже."

        record_outbox("sent", None)
        email_record = {
            "id": outbox_id,
            "recipient": recipient,
            "subject": subject,
            "body_text": body_text,
            "status": "sent",
            "created_at": now_iso
        }
        email_record.update(extra or {})
        with self._lock:
            self.sent_emails.append(email_record)
        return True, None


EMAIL_SERVICE = EmailService()


def send_verification_email(
    conn: sqlite3.Connection,
    recipient: str,
    code: str,
    login: str
) -> Tuple[bool, Optional[str]]:
    return EMAIL_SERVICE.send_verification_email(conn, recipient, code, login)
