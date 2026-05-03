from __future__ import annotations

import logging
import os
from typing import Dict, List

from flask import Flask

from .db import session_scope
from .models import NotificationEvent


_logger = logging.getLogger("recognition_portal.notifications")


def init_notifications(app: Flask) -> None:
    app.extensions["notification_outbox"] = []


def send_email(app: Flask, event_type: str, recipient_email: str, subject: str, body: str) -> None:
    payload = {
        "event_type": event_type,
        "recipient_email": recipient_email,
        "subject": subject,
        "body": body,
    }
    _store_event(app, payload)
    app.extensions["notification_outbox"].append(payload)
    if _email_logging_enabled():
        _logger.info(
            "email event_type=%s recipient=%s subject=%s",
            event_type,
            recipient_email,
            subject,
        )
        _logger.debug("email body event_type=%s body=%r", event_type, body)


def _store_event(app: Flask, payload: Dict[str, str]) -> None:
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
