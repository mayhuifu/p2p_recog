from __future__ import annotations

import hashlib
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import wraps
from threading import Lock
from typing import Callable, Deque, Dict, Optional

from flask import Flask, flash, g, redirect, request, session, url_for
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

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


class LoginRateLimitError(ValueError):
    pass


class _LoginRateLimiter:
    def __init__(self) -> None:
        self._lock = Lock()
        self._email_hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._ip_hits: Dict[str, Deque[float]] = defaultdict(deque)

    def check(
        self,
        *,
        email: str,
        ip: Optional[str],
        per_email: int,
        per_ip: int,
        window_seconds: int,
    ) -> None:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            email_hits = self._trim(self._email_hits[email], cutoff)
            if len(email_hits) >= per_email:
                raise LoginRateLimitError(
                    "Too many sign-in requests for that email. Wait a few minutes and try again."
                )
            if ip:
                ip_hits = self._trim(self._ip_hits[ip], cutoff)
                if len(ip_hits) >= per_ip:
                    raise LoginRateLimitError(
                        "Too many sign-in requests from this device. Wait a few minutes and try again."
                    )
                ip_hits.append(now)
            email_hits.append(now)

    @staticmethod
    def _trim(hits: Deque[float], cutoff: float) -> Deque[float]:
        while hits and hits[0] < cutoff:
            hits.popleft()
        return hits

    def clear(self) -> None:
        with self._lock:
            self._email_hits.clear()
            self._ip_hits.clear()


def register_auth(app: Flask) -> None:
    app.extensions["login_rate_limiter"] = _LoginRateLimiter()

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
    _enforce_login_rate_limit(app, email=normalized_email, ip=requested_by_ip)
    _purge_stale_tokens(db_session)

    token = secrets.token_urlsafe(24)
    login_token = LoginToken(
        email=normalized_email,
        token_hash=hash_token(token),
        requested_by_ip=requested_by_ip,
        expires_at=_utc_now() + timedelta(minutes=app.config["MAGIC_LINK_TTL_MINUTES"]),
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
    if _ensure_aware(token.expires_at) < _utc_now():
        token.status = "expired"
        raise ValueError("That sign-in link has expired. Request a new one.")

    token.status = "consumed"
    token.consumed_at = _utc_now()
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


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _enforce_login_rate_limit(app: Flask, *, email: str, ip: Optional[str]) -> None:
    limiter: _LoginRateLimiter = app.extensions["login_rate_limiter"]
    limiter.check(
        email=email,
        ip=ip,
        per_email=app.config["LOGIN_RATE_LIMIT_PER_EMAIL"],
        per_ip=app.config["LOGIN_RATE_LIMIT_PER_IP"],
        window_seconds=app.config["LOGIN_RATE_LIMIT_WINDOW_SECONDS"],
    )


def _purge_stale_tokens(db_session: Session) -> None:
    cutoff = _utc_now() - timedelta(days=7)
    db_session.execute(
        delete(LoginToken).where(LoginToken.expires_at < cutoff)
    )
