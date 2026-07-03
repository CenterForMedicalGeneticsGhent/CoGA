import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_reject_insecure_defaults_outside_development() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            APP_ENV="production",
            SECRET_KEY="change-me",
            POSTGRES_PASSWORD="change-me",
            ADMIN_PASSWORD="change-me",
        )


def test_settings_allow_placeholder_defaults_in_test_env() -> None:
    settings = Settings(
        _env_file=None,
        APP_ENV="test",
    )

    assert settings.is_development is True


def test_settings_reject_audit_log_drop_allowed_in_production() -> None:
    # Silently dropping accountability events is not permitted in production.
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            APP_ENV="production",
            SECRET_KEY="x" * 48,
            POSTGRES_PASSWORD="s3cure-pg-pass",
            ADMIN_PASSWORD="s3cure-admin-pass",
            AUDIT_LOG_DROP_ALLOWED=True,
        )


def test_settings_allow_audit_log_drop_allowed_in_development() -> None:
    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        AUDIT_LOG_DROP_ALLOWED=True,
    )

    assert settings.audit_log_drop_allowed is True


def test_cors_origin_regex_default_is_fully_anchored() -> None:
    settings = Settings(_env_file=None, APP_ENV="test")
    assert settings.cors_origin_regex.startswith("^")
    assert settings.cors_origin_regex.endswith("$")


def test_cors_origin_regex_accepts_anchored_pattern() -> None:
    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        CORS_ORIGIN_REGEX=r"^https://app\.example\.org$",
    )
    assert settings.cors_origin_regex == r"^https://app\.example\.org$"


def test_cors_origin_regex_empty_is_allowed() -> None:
    settings = Settings(_env_file=None, APP_ENV="test", CORS_ORIGIN_REGEX="")
    assert settings.cors_origin_regex == ""


def test_cors_origin_regex_rejects_unanchored_pattern() -> None:
    # An unanchored pattern could match a hostile origin as a substring while
    # allow_credentials=True — reject it at load time.
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            APP_ENV="test",
            CORS_ORIGIN_REGEX=r"https://app\.example\.org",
        )


def test_cors_origin_regex_rejects_invalid_regex() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            APP_ENV="test",
            CORS_ORIGIN_REGEX=r"^https://(unclosed$",
        )


def test_postgres_connect_args_reflects_sslmode() -> None:
    # Default (disable) -> plain connection, no ssl arg.
    assert Settings(_env_file=None, APP_ENV="test").postgres_connect_args == {}
    # An enabled mode is passed through to asyncpg as `ssl`.
    secured = Settings(_env_file=None, APP_ENV="test", POSTGRES_SSLMODE="require")
    assert secured.postgres_connect_args == {"ssl": "require"}


def test_invalid_postgres_sslmode_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, APP_ENV="test", POSTGRES_SSLMODE="bogus")


def test_clickhouse_tls_defaults_off() -> None:
    default = Settings(_env_file=None, APP_ENV="test")
    assert default.clickhouse_secure is False
    assert default.clickhouse_verify is True

    secure = Settings(_env_file=None, APP_ENV="test", CLICKHOUSE_SECURE=True)
    assert secure.clickhouse_secure is True
