from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage
from typing import Dict, List, Optional

from flask import Flask
from sqlalchemy.orm import Session

from .db import session_scope
from .models import NotificationEvent


_logger = logging.getLogger("recognition_portal.notifications")


def init_notifications(app: Flask) -> None:
    app.extensions["notification_outbox"] = []


def send_email(
    app: Flask,
    event_type: str,
    recipient_email: str,
    subject: str,
    body: str,
    *,
    db_session: Optional[Session] = None,
) -> None:
    payload = {
        "event_type": event_type,
        "recipient_email": recipient_email,
        "subject": subject,
        "body": body,
    }
    _store_event(app, payload, db_session=db_session)
    app.extensions["notification_outbox"].append(payload)
    if _smtp_enabled(app):
        _deliver_via_smtp(app, payload)
    if _email_logging_enabled():
        _logger.info(
            "email event_type=%s recipient=%s subject=%s",
            event_type,
            recipient_email,
            subject,
        )
        _logger.debug("email body event_type=%s body=%r", event_type, body)


def _store_event(app: Flask, payload: Dict[str, str], *, db_session: Optional[Session]) -> None:
    if db_session is not None:
        db_session.add(
            NotificationEvent(
                event_type=payload["event_type"],
                recipient_email=payload["recipient_email"],
                subject=payload["subject"],
                body=payload["body"],
            )
        )
        return

    with session_scope(app) as session:
        session.add(
            NotificationEvent(
                event_type=payload["event_type"],
                recipient_email=payload["recipient_email"],
                subject=payload["subject"],
                body=payload["body"],
            )
        )


def delivered_messages(app: Flask) -> List[Dict[str, str]]:
    return list(app.extensions["notification_outbox"])


def _email_logging_enabled() -> bool:
    return os.getenv("LOG_EMAIL_EVENTS", "true").strip().lower() not in {"0", "false", "no"}


def _smtp_enabled(app: Flask) -> bool:
    return bool(app.config.get("SMTP_HOST") and app.config.get("SMTP_FROM_EMAIL"))


def _deliver_via_smtp(app: Flask, payload: Dict[str, str]) -> None:
    message = EmailMessage()
    message["From"] = app.config["SMTP_FROM_EMAIL"]
    message["To"] = payload["recipient_email"]
    message["Subject"] = payload["subject"]
    message.set_content(payload["body"])

    host = app.config["SMTP_HOST"]
    port = app.config["SMTP_PORT"]
    timeout = app.config["SMTP_TIMEOUT_SECONDS"]
    username = app.config.get("SMTP_USERNAME")
    password = app.config.get("SMTP_PASSWORD")
    use_ssl = app.config.get("SMTP_USE_SSL", False)
    use_tls = app.config.get("SMTP_USE_TLS", True)

    smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    with smtp_class(host, port, timeout=timeout) as smtp:
        if not use_ssl and use_tls:
            smtp.starttls()
        if username:
            smtp.login(username, password or "")
        smtp.send_message(message)
