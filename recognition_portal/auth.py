from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import wraps
from typing import Callable, Optional

from flask import Flask, flash, g, redirect, request, session, url_for
from sqlalchemy import select
from sqlalchemy.orm import Session

from .employee_directory import list_employees
from .models import Employee, LoginToken
from .notifications import send_email


@dataclass
class SessionUser:
    email: str
    role: str
    access_state: str
    employee_id: Optional[int]
    display_name: str

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_active_employee(self) -> bool:
        return self.access_state == "active"


def register_auth(app: Flask) -> None:
    @app.before_request
    def load_user() -> None:
        data = session.get("user_session")
        g.current_user = SessionUser(**data) if data else None

    @app.context_processor
    def inject_user():
        return {"current_user": getattr(g, "current_user", None)}


def create_magic_link_request(app: Flask, db_session: Session, email: str, requested_by_ip: Optional[str]) -> LoginToken:
    normalized_email = normalize_email(email)
    ensure_company_domain(app, normalized_email)

    token = secrets.token_urlsafe(24)
    login_token = LoginToken(
        email=normalized_email,
        token_hash=hash_token(token),
        requested_by_ip=requested_by_ip,
        expires_at=datetime.utcnow() + timedelta(minutes=app.config["MAGIC_LINK_TTL_MINUTES"]),
    )
    db_session.add(login_token)
    db_session.flush()

    send_email(
        app,
        event_type="magic_link",
        recipient_email=normalized_email,
        subject="Your P2P Recognition sign-in link",
        body=build_magic_link_email(app, token),
    )
    return login_token


def consume_magic_link(db_session: Session, raw_token: str) -> LoginToken:
    token_hash = hash_token(raw_token)
    token = db_session.scalar(select(LoginToken).where(LoginToken.token_hash == token_hash))
    if token is None:
        raise ValueError("That sign-in link is not valid.")
    if token.status != "pending":
        raise ValueError("That sign-in link has already been used.")
    if token.expires_at < datetime.utcnow():
        token.status = "expired"
        raise ValueError("That sign-in link has expired. Request a new one.")

    token.status = "consumed"
    token.consumed_at = datetime.utcnow()
    return token


def build_session_user(db_session: Session, email: str) -> SessionUser:
    employee = db_session.scalar(select(Employee).where(Employee.email == normalize_email(email)))
    if employee is None:
        return SessionUser(
            email=normalize_email(email),
            role="pending_access",
            access_state="pending_directory",
            employee_id=None,
            display_name=normalize_email(email),
        )

    access_state = "active" if employee.can_participate else "inactive"
    return SessionUser(
        email=employee.email,
        role=employee.role,
        access_state=access_state,
        employee_id=employee.id,
        display_name=employee.name,
    )


def login_required(view: Callable):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if getattr(g, "current_user", None) is None:
            flash("Sign in to continue.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def active_employee_required(view: Callable):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        user = g.current_user
        if not user.is_active_employee:
            flash("Your account is signed in but not active for portal actions yet.", "warning")
            return redirect(url_for("portal_home"))
        return view(*args, **kwargs)

    return wrapped


def role_required(*roles: str):
    def decorator(view: Callable):
        @wraps(view)
        @active_employee_required
        def wrapped(*args, **kwargs):
            user = g.current_user
            if user.role not in roles:
                flash("You do not have access to that page.", "danger")
                return redirect(url_for("portal_home"))
            return view(*args, **kwargs)

        return wrapped

    return decorator


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def ensure_company_domain(app: Flask, email: str) -> None:
    allowed_domains = app.config.get("ALLOWED_LOGIN_DOMAINS", [])
    if not allowed_domains:
        return
    domain = email.partition("@")[2]
    if domain not in allowed_domains:
        raise ValueError("Use an approved company email domain.")


def build_magic_link_email(app: Flask, raw_token: str) -> str:
    base_url = app.config.get("PUBLIC_BASE_URL", "http://localhost:5000").rstrip("/")
    login_url = f"{base_url}{url_for('consume_login_token', token=raw_token)}"
    return (
        "Use this sign-in link to access the P2P Recognition portal.\n\n"
        f"{login_url}\n\n"
        f"This link expires in {app.config['MAGIC_LINK_TTL_MINUTES']} minutes."
    )
