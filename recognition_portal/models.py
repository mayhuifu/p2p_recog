from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="employee")
    department: Mapped[Optional[str]] = mapped_column(String(120))
    region: Mapped[Optional[str]] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    manager_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    manager: Mapped[Optional["Employee"]] = relationship(
        "Employee",
        remote_side="Employee.id",
        backref="reports",
    )

    @property
    def can_participate(self) -> bool:
        return self.is_active

    def __repr__(self) -> str:
        return f"<Employee {self.email}>"


class LoginToken(Base):
    __tablename__ = "login_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    requested_by_ip: Mapped[Optional[str]] = mapped_column(String(64))
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class NotificationEvent(Base):
    __tablename__ = "notification_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class Recognition(Base):
    __tablename__ = "recognitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    recognition_type: Mapped[str] = mapped_column(String(32), nullable=False, default="non_monetary")
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    company_value: Mapped[Optional[str]] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="published")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    sender: Mapped["Employee"] = relationship("Employee", foreign_keys=[sender_id])
    recipient: Mapped["Employee"] = relationship("Employee", foreign_keys=[recipient_id])


class RecognitionModerationAction(Base):
    __tablename__ = "recognition_moderation_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recognition_id: Mapped[int] = mapped_column(ForeignKey("recognitions.id"), nullable=False, index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    action_type: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    recognition: Mapped["Recognition"] = relationship("Recognition")
    actor: Mapped["Employee"] = relationship("Employee")
