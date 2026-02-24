from app.settings import Settings


def test_settings_defaults_to_debug_in_local() -> None:
    settings = Settings(APP_ENV="local", LOG_LEVEL=None)
    assert settings.effective_log_level == "DEBUG"


def test_settings_defaults_to_info_in_non_local() -> None:
    settings = Settings(APP_ENV="cluster", LOG_LEVEL=None)
    assert settings.effective_log_level == "INFO"


def test_settings_honors_explicit_log_level() -> None:
    settings = Settings(APP_ENV="local", LOG_LEVEL="WARNING")
    assert settings.effective_log_level == "WARNING"
