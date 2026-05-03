from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session, selectinload

from .models import Employee, Recognition
from .notifications import send_email


RECOGNITION_CATEGORIES = [
    "Teamwork",
    "Ownership",
    "Innovation",
    "Customer Impact",
    "Above and Beyond",
]

COMPANY_VALUES = [
    "Craft",
    "Trust",
    "Speed",
    "Ownership",
    "Customer Care",
]


class RecognitionValidationError(ValueError):
    pass


@dataclass
class RecognitionCreateInput:
    sender_id: int
    recipient_id: int
    category: str
    company_value: Optional[str]
    message: str


def create_non_monetary_recognition(app, db_session: Session, payload: RecognitionCreateInput) -> Recognition:
    sender = db_session.get(Employee, payload.sender_id)
    recipient = db_session.get(Employee, payload.recipient_id)
    if sender is None or recipient is None:
        raise RecognitionValidationError("Select a valid employee recipient.")
    if not sender.can_participate:
        raise RecognitionValidationError("Your employee record is not active yet.")
    if not recipient.can_participate:
        raise RecognitionValidationError("The selected recipient is not active in the portal.")
    if sender.id == recipient.id:
        raise RecognitionValidationError("You cannot recognize yourself.")

    category = payload.category.strip()
    if category not in RECOGNITION_CATEGORIES:
        raise RecognitionValidationError("Choose a valid recognition category.")

    company_value = (payload.company_value or "").strip() or None
    if company_value is not None and company_value not in COMPANY_VALUES:
        raise RecognitionValidationError("Choose a valid company value.")

    message = payload.message.strip()
    if len(message) < 20:
        raise RecognitionValidationError("Recognition message must be at least 20 characters.")
    if len(message) > 500:
        raise RecognitionValidationError("Recognition message must be 500 characters or fewer.")

    duplicate_cutoff = datetime.utcnow() - timedelta(days=14)
    duplicate_stmt = (
        select(Recognition)
        .where(Recognition.sender_id == sender.id)
        .where(Recognition.recipient_id == recipient.id)
        .where(Recognition.recognition_type == "non_monetary")
        .where(Recognition.published_at >= duplicate_cutoff)
        .order_by(Recognition.published_at.desc())
    )
    if db_session.scalar(duplicate_stmt) is not None:
        raise RecognitionValidationError(
            "You already recognized this coworker in the last 14 days. Try again later."
        )

    recognition = Recognition(
        sender=sender,
        recipient=recipient,
        category=category,
        company_value=company_value,
        message=message,
        recognition_type="non_monetary",
        status="published",
    )
    db_session.add(recognition)
    db_session.flush()

    send_email(
        app,
        event_type="non_monetary_recognition_recipient",
        recipient_email=recipient.email,
        subject=f"{sender.name} recognized your work",
        body=(
            f"{sender.name} recognized you for {category}.\n\n"
            f"Message:\n{message}"
        ),
    )
    if recipient.manager is not None:
        send_email(
            app,
            event_type="non_monetary_recognition_manager",
            recipient_email=recipient.manager.email,
            subject=f"{recipient.name} was recognized",
            body=(
                f"{sender.name} recognized {recipient.name} for {category}.\n\n"
                f"Message:\n{message}"
            ),
        )

    return recognition


def list_feed_recognitions(db_session: Session, limit: int = 10) -> list[Recognition]:
    stmt = (
        select(Recognition)
        .options(selectinload(Recognition.sender), selectinload(Recognition.recipient))
        .where(Recognition.status == "published")
        .where(Recognition.recognition_type == "non_monetary")
        .order_by(desc(Recognition.published_at), desc(Recognition.id))
        .limit(limit)
    )
    return list(db_session.scalars(stmt))


def list_employee_recognitions(db_session: Session, employee_id: int, limit: int = 5) -> tuple[list[Recognition], list[Recognition]]:
    base_stmt = (
        select(Recognition)
        .options(selectinload(Recognition.sender), selectinload(Recognition.recipient))
        .where(Recognition.status == "published")
        .where(Recognition.recognition_type == "non_monetary")
        .order_by(desc(Recognition.published_at), desc(Recognition.id))
        .limit(limit)
    )
    sent = list(
        db_session.scalars(
            base_stmt.where(Recognition.sender_id == employee_id)
        )
    )
    received = list(
        db_session.scalars(
            base_stmt.where(Recognition.recipient_id == employee_id)
        )
    )
    return sent, received
