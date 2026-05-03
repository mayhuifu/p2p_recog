from __future__ import annotations

from typing import Optional

from flask import Flask

from .auth import register_auth
from .db import database_url_from_env, init_database
from .notifications import init_notifications
from .web import register_routes


def create_app(test_config: Optional[dict] = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True, template_folder="../templates")
    app.config.from_mapping(
        SECRET_KEY="dev",
        DATABASE_URL=database_url_from_env(app.instance_path),
        ALLOWED_LOGIN_DOMAINS=["example.com"],
        MAGIC_LINK_TTL_MINUTES=30,
        PUBLIC_BASE_URL="http://localhost:5000",
    )
    if test_config:
        app.config.update(test_config)

    init_database(app)
    init_notifications(app)
    register_auth(app)
    register_routes(app)
    return app
