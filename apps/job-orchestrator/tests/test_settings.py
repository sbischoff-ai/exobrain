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


def test_settings_builds_api_bind_target_from_host_port() -> None:
    settings = Settings(JOB_ORCHESTRATOR_API_HOST="127.0.0.1", JOB_ORCHESTRATOR_API_PORT=6000)
    assert settings.job_orchestrator_api_bind_target == "127.0.0.1:6000"


def test_settings_prefers_explicit_api_bind_address() -> None:
    settings = Settings(
        JOB_ORCHESTRATOR_API_HOST="127.0.0.1",
        JOB_ORCHESTRATOR_API_PORT=6000,
        JOB_ORCHESTRATOR_API_BIND_ADDRESS="0.0.0.0:50061",
    )
    assert settings.job_orchestrator_api_bind_target == "0.0.0.0:50061"
