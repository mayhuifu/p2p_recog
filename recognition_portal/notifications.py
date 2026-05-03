from __future__ import annotations

from typing import Dict, List

from flask import Flask
from sqlalchemy.orm import Session

from .db import session_scope
from .models import NotificationEvent


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
    print(f"[EMAIL] To: {recipient_email}\nSubject: {subject}\n\n{body}\n")


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
