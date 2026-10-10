"""Application settings, read from environment variables (and a local .env file)."""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
MIN_SECRET_KEY_LENGTH = 16
PLACEHOLDER_PREFIX = "change-this"

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


class ConfigError(ValueError):
    """A setting is missing or invalid. Messages never contain secret values."""


def _get_str(env: Mapping[str, str], name: str, default: str = "") -> str:
    return env.get(name, default).strip()


def _get_int(env: Mapping[str, str], name: str, default: int, minimum: int, maximum: int) -> int:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        raise ConfigError(f"{name} must be a whole number, got {raw!r}") from None
    if not minimum <= value <= maximum:
        raise ConfigError(f"{name} must be between {minimum} and {maximum}, got {value}")
    return value


def _get_bool(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ConfigError(f"{name} must be true or false, got {raw!r}")


def validate_secret_key(value: str) -> None:
    """Refuse to start with a missing, placeholder or too-short SECRET_KEY."""
    if not value or not value.strip():
        raise ConfigError("SECRET_KEY is not set. Put a long random value in your .env file.")
    if value.startswith(PLACEHOLDER_PREFIX):
        raise ConfigError("SECRET_KEY still has the example placeholder. Replace it in your .env file.")
    if len(value) < MIN_SECRET_KEY_LENGTH:
        raise ConfigError(f"SECRET_KEY is too short (minimum {MIN_SECRET_KEY_LENGTH} characters).")


@dataclass(frozen=True)
class Settings:
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = field(default="", repr=False)
    db_name: str = "shop_db"
    db_ssl_disabled: bool = True
    db_connect_timeout: int = 5
    secret_key: str = field(default="", repr=False)
    cookie_secure: bool = False
    debug: bool = False
    host: str = "127.0.0.1"
    port: int = 5000

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if env is None else env
        db_host = _get_str(env, "DB_HOST", "127.0.0.1") or "127.0.0.1"
        secret_key = _get_str(env, "SECRET_KEY")
        validate_secret_key(secret_key)
        return cls(
            db_host=db_host,
            db_port=_get_int(env, "DB_PORT", 3306, 1, 65535),
            db_user=_get_str(env, "DB_USER", "root") or "root",
            db_password=env.get("DB_PASSWORD", ""),
            db_name=_get_str(env, "DB_NAME", "shop_db") or "shop_db",
            # Traffic to a database on this same computer never leaves it, so TLS is
            # off by default there. For any other host TLS is left on (PyMySQL default).
            db_ssl_disabled=_get_bool(env, "DB_SSL_DISABLED", db_host.lower() in LOOPBACK_HOSTS),
            db_connect_timeout=_get_int(env, "DB_CONNECT_TIMEOUT", 5, 1, 60),
            secret_key=secret_key,
            cookie_secure=_get_bool(env, "SESSION_COOKIE_SECURE", False),
            debug=_get_bool(env, "APP_DEBUG", False),
            host=_get_str(env, "APP_HOST", "127.0.0.1") or "127.0.0.1",
            port=_get_int(env, "APP_PORT", 5000, 1, 65535),
        )
