from app.core.config import Settings


def test_default_cors_origins_cover_local_frontend_ports() -> None:
    settings = Settings(_env_file=None)

    assert "http://localhost:3000" in settings.cors_origins
    assert "http://localhost:5173" in settings.cors_origins
    assert settings.postgres_db == "coga"
    assert settings.clickhouse_database == "coga"


def test_cors_origins_support_comma_separated_env_values() -> None:
    settings = Settings(
        _env_file=None,
        CORS_ORIGINS="http://localhost:3000, http://localhost:5173",
    )

    assert settings.cors_origins == [
        "http://localhost:3000",
        "http://localhost:5173",
    ]


def test_build_identity_has_safe_local_defaults() -> None:
    # Unstamped local/dev build: honest sentinels, never blank — so /version and the
    # frozen sign-out snapshot record "unknown" rather than failing or hiding it.
    settings = Settings(_env_file=None)
    assert settings.app_version == "0.0.0+unknown"
    assert settings.git_sha == "unknown"


def test_build_identity_reads_from_env() -> None:
    settings = Settings(_env_file=None, APP_VERSION="1.2.3", GIT_SHA="abc1234def5")
    assert settings.app_version == "1.2.3"
    assert settings.git_sha == "abc1234def5"
