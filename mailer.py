"""Minimal SMTP delivery for verification and password-reset messages."""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage


class MailError(Exception):
    pass


def is_configured() -> bool:
    return bool(
        os.getenv("SMTP_HOST", "").strip()
        and os.getenv("SMTP_FROM", "").strip()
    )


def send_email(to_email: str, subject: str, text: str) -> None:
    if not is_configured():
        raise MailError("Email delivery is not configured.")

    host = os.getenv("SMTP_HOST", "").strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "")
    from_email = os.getenv("SMTP_FROM", "").strip()
    use_ssl = os.getenv("SMTP_SSL", "false").strip().lower() in {"1", "true", "yes"}
    use_starttls = os.getenv("SMTP_STARTTLS", "true").strip().lower() in {"1", "true", "yes"}

    message = EmailMessage()
    message["From"] = from_email
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(text)

    try:
        if use_ssl:
            with smtplib.SMTP_SSL(
                host,
                port,
                timeout=15,
                context=ssl.create_default_context(),
            ) as server:
                if username:
                    server.login(username, password)
                server.send_message(message)
            return

        with smtplib.SMTP(host, port, timeout=15) as server:
            server.ehlo()
            if use_starttls:
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
            if username:
                server.login(username, password)
            server.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise MailError("Email delivery failed.") from exc
