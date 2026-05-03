from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session, selectinload

from .models import (
    Employee,
    PointsRecognitionRecipient,
    PointsRecognitionRequest,
    Recognition,
    RecognitionModerationAction,
)
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

POINTS_PRESET_OPTIONS = [10, 25, 50]


class RecognitionValidationError(ValueError):
    pass


class RecognitionModerationError(ValueError):
    pass


class PointsRecognitionError(ValueError):
    pass


@dataclass
class RecognitionCreateInput:
    sender_id: int
    recipient_id: int
    category: str
    company_value: Optional[str]
    message: str


@dataclass
class PointsRecognitionInput:
    sender_id: int
    recipient_ids: list[int]
    category: str
    company_value: Optional[str]
    message: str
    points: int


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


def list_all_recognitions_for_admin(db_session: Session, limit: int = 30) -> list[Recognition]:
    stmt = (
        select(Recognition)
        .options(selectinload(Recognition.sender), selectinload(Recognition.recipient))
        .order_by(desc(Recognition.published_at), desc(Recognition.id))
        .limit(limit)
    )
    return list(db_session.scalars(stmt))


def create_points_recognition_request(
    db_session: Session,
    payload: PointsRecognitionInput,
) -> PointsRecognitionRequest:
    sender, recipients, category, company_value, message, points = _validate_points_request_input(
        db_session,
        payload,
    )
    request = PointsRecognitionRequest(
        sender=sender,
        category=category,
        company_value=company_value,
        message=message,
        requested_points_per_recipient=points,
        status="pending_approval",
        recipients=[
            PointsRecognitionRecipient(recipient=recipient)
            for recipient in recipients
        ],
    )
    db_session.add(request)
    db_session.flush()
    return request


def update_points_recognition_request(
    db_session: Session,
    *,
    request_id: int,
    sender_id: int,
    payload: PointsRecognitionInput,
) -> PointsRecognitionRequest:
    request = _get_points_request_for_sender(db_session, request_id=request_id, sender_id=sender_id)
    if request.status != "pending_approval":
        raise PointsRecognitionError("Only pending points recognitions can be edited.")

    sender, recipients, category, company_value, message, points = _validate_points_request_input(
        db_session,
        payload,
    )
    request.sender = sender
    request.category = category
    request.company_value = company_value
    request.message = message
    request.requested_points_per_recipient = points
    request.status = "pending_approval"
    request.recipients.clear()
    request.recipients.extend(
        PointsRecognitionRecipient(recipient=recipient)
        for recipient in recipients
    )
    db_session.flush()
    return request


def cancel_points_recognition_request(
    db_session: Session,
    *,
    request_id: int,
    sender_id: int,
) -> PointsRecognitionRequest:
    request = _get_points_request_for_sender(db_session, request_id=request_id, sender_id=sender_id)
    if request.status != "pending_approval":
        raise PointsRecognitionError("Only pending points recognitions can be canceled.")
    request.status = "canceled"
    db_session.flush()
    return request


def delete_points_recognition_request(
    db_session: Session,
    *,
    request_id: int,
    sender_id: int,
) -> None:
    request = _get_points_request_for_sender(db_session, request_id=request_id, sender_id=sender_id)
    if request.status != "pending_approval":
        raise PointsRecognitionError("Only pending points recognitions can be deleted.")
    db_session.delete(request)
    db_session.flush()


def get_points_recognition_request_for_sender(
    db_session: Session,
    *,
    request_id: int,
    sender_id: int,
) -> PointsRecognitionRequest:
    return _get_points_request_for_sender(db_session, request_id=request_id, sender_id=sender_id)


def list_points_recognition_requests_for_sender(
    db_session: Session,
    *,
    sender_id: int,
    limit: int = 10,
) -> list[PointsRecognitionRequest]:
    stmt = (
        select(PointsRecognitionRequest)
        .options(
            selectinload(PointsRecognitionRequest.sender),
            selectinload(PointsRecognitionRequest.recipients).selectinload(PointsRecognitionRecipient.recipient),
        )
        .where(PointsRecognitionRequest.sender_id == sender_id)
        .order_by(desc(PointsRecognitionRequest.updated_at), desc(PointsRecognitionRequest.id))
        .limit(limit)
    )
    return list(db_session.scalars(stmt))


def can_moderate_recognition(actor: Employee, recognition: Recognition) -> bool:
    if actor.role == "admin":
        return True
    sender_manager_id = recognition.sender.manager_id
    recipient_manager_id = recognition.recipient.manager_id
    return actor.id in {sender_manager_id, recipient_manager_id}


def moderate_recognition(
    app,
    db_session: Session,
    *,
    recognition_id: int,
    actor_id: int,
    action_type: str,
    reason: str,
) -> Recognition:
    recognition = db_session.scalar(
        select(Recognition)
        .options(selectinload(Recognition.sender), selectinload(Recognition.recipient))
        .where(Recognition.id == recognition_id)
    )
    actor = db_session.get(Employee, actor_id)
    if recognition is None or actor is None:
        raise RecognitionModerationError("Recognition or moderator not found.")
    if recognition.recognition_type != "non_monetary":
        raise RecognitionModerationError("Only published non-monetary recognition can be moderated here.")
    if recognition.status not in {"published", "hidden", "removed"}:
        raise RecognitionModerationError("Recognition is not in a moderatable state.")
    if action_type not in {"hidden", "removed"}:
        raise RecognitionModerationError("Unsupported moderation action.")
    if not reason.strip():
        raise RecognitionModerationError("Moderation reason is required.")
    if not can_moderate_recognition(actor, recognition):
        raise RecognitionModerationError("You do not have permission to moderate this recognition.")

    recognition.status = action_type
    db_session.add(
        RecognitionModerationAction(
            recognition=recognition,
            actor=actor,
            action_type=action_type,
            reason=reason.strip(),
        )
    )
    db_session.flush()

    send_email(
        app,
        event_type=f"recognition_{action_type}",
        recipient_email=recognition.sender.email,
        subject=f"Your recognition was {action_type}",
        body=(
            f"Your recognition for {recognition.recipient.name} was {action_type} by {actor.name}.\n\n"
            f"Reason:\n{reason.strip()}"
        ),
    )
    return recognition


def _validate_points_request_input(
    db_session: Session,
    payload: PointsRecognitionInput,
) -> tuple[Employee, list[Employee], str, Optional[str], str, int]:
    sender = db_session.get(Employee, payload.sender_id)
    if sender is None or not sender.can_participate:
        raise PointsRecognitionError("Your employee record is not active yet.")

    if not payload.recipient_ids:
        raise PointsRecognitionError("Select at least one coworker.")

    if len(set(payload.recipient_ids)) != len(payload.recipient_ids):
        raise PointsRecognitionError("Select each recipient only once.")

    recipients = []
    for recipient_id in payload.recipient_ids:
        recipient = db_session.get(Employee, recipient_id)
        if recipient is None:
            raise PointsRecognitionError("Select valid employee recipients.")
        if not recipient.can_participate:
            raise PointsRecognitionError("All selected recipients must be active employees.")
        if recipient.id == sender.id:
            raise PointsRecognitionError("You cannot recognize yourself with points.")
        if recipient.role == "executive":
            raise PointsRecognitionError("Executives can only receive non-monetary recognition.")
        recipients.append(recipient)

    category = payload.category.strip()
    if category not in RECOGNITION_CATEGORIES:
        raise PointsRecognitionError("Choose a valid recognition category.")

    company_value = (payload.company_value or "").strip() or None
    if company_value is not None and company_value not in COMPANY_VALUES:
        raise PointsRecognitionError("Choose a valid company value.")

    message = payload.message.strip()
    if len(message) < 20:
        raise PointsRecognitionError("Recognition message must be at least 20 characters.")
    if len(message) > 500:
        raise PointsRecognitionError("Recognition message must be 500 characters or fewer.")

    if payload.points not in POINTS_PRESET_OPTIONS:
        raise PointsRecognitionError("Choose a valid points amount.")

    return sender, recipients, category, company_value, message, payload.points


def _get_points_request_for_sender(
    db_session: Session,
    *,
    request_id: int,
    sender_id: int,
) -> PointsRecognitionRequest:
    request = db_session.scalar(
        select(PointsRecognitionRequest)
        .options(
            selectinload(PointsRecognitionRequest.sender),
            selectinload(PointsRecognitionRequest.recipients).selectinload(PointsRecognitionRecipient.recipient),
        )
        .where(PointsRecognitionRequest.id == request_id)
        .where(PointsRecognitionRequest.sender_id == sender_id)
    )
    if request is None:
        raise PointsRecognitionError("Points recognition request not found.")
    return request
