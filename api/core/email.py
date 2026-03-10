"""SMTP email delivery for enrollment and notifications."""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from core.config import settings

logger = logging.getLogger(__name__)


class EmailNotConfiguredError(Exception):
    """Raised when SMTP settings are missing."""


def send_email(to: str, subject: str, html_body: str, text_body: str | None = None) -> None:
    """Send an email via SMTP. Raises EmailNotConfiguredError if SMTP is not set up."""
    if not settings.smtp_configured:
        raise EmailNotConfiguredError(
            "Email delivery is not configured. Set SMTP_HOST and SMTP_FROM in the server environment."
        )

    msg = MIMEMultipart("alternative")
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject

    if text_body:
        msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        if settings.smtp_use_tls:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
            server.starttls()
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)

        if settings.smtp_user and settings.smtp_password:
            server.login(settings.smtp_user, settings.smtp_password)

        server.sendmail(settings.smtp_from, to, msg.as_string())
        server.quit()
        logger.info("Email sent to %s: %s", to, subject)
    except smtplib.SMTPException:
        logger.exception("Failed to send email to %s", to)
        raise
