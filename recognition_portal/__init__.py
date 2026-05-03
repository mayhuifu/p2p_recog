from __future__ import annotations

import os
from typing import Optional

from flask import Flask

from .auth import register_auth
from .db import database_url_from_env, init_database
from .notifications import init_notifications
from .web import register_routes


def create_app(test_config: Optional[dict] = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY"),
        DATABASE_URL=database_url_from_env(app.instance_path),
        ALLOWED_LOGIN_DOMAINS=_split_env_list("ALLOWED_LOGIN_DOMAINS", default=["example.com"]),
        MAGIC_LINK_TTL_MINUTES=int(os.getenv("MAGIC_LINK_TTL_MINUTES", "30")),
        PUBLIC_BASE_URL=os.getenv("PUBLIC_BASE_URL", "http://localhost:5000"),
        LOGIN_RATE_LIMIT_PER_EMAIL=int(os.getenv("LOGIN_RATE_LIMIT_PER_EMAIL", "3")),
        LOGIN_RATE_LIMIT_PER_IP=int(os.getenv("LOGIN_RATE_LIMIT_PER_IP", "10")),
        LOGIN_RATE_LIMIT_WINDOW_SECONDS=int(os.getenv("LOGIN_RATE_LIMIT_WINDOW_SECONDS", "300")),
    )
    if test_config:
        app.config.update(test_config)

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY env var must be set (or provided via test_config).")

    init_database(app)
    init_notifications(app)
    register_auth(app)
    register_routes(app)
    return app


def _split_env_list(env_name: str, *, default: list[str]) -> list[str]:
    raw = os.getenv(env_name)
    if not raw:
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]
