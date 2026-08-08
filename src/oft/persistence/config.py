"""Database configuration: resolve the connection string from the environment."""

from __future__ import annotations

import os

_DEFAULT_DSN = "postgresql://oft:change_me_locally@127.0.0.1:5442/oft"


def database_url() -> str:
    return os.environ.get("DATABASE_URL", _DEFAULT_DSN)
