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


def test_settings_uses_local_model_provider_default() -> None:
    settings = Settings()
    assert settings.model_provider_base_url == "http://localhost:8010/v1"


def test_settings_normalizes_model_provider_base_url() -> None:
    settings = Settings(MODEL_PROVIDER_BASE_URL="http://provider")
    assert settings.model_provider_base_url == "http://provider/v1"


def test_settings_defaults_knowledge_update_model_provider_timeout() -> None:
    settings = Settings()
    assert settings.knowledge_update_model_provider_timeout_seconds == 120.0


def test_settings_defaults_consumer_ack_wait_seconds() -> None:
    settings = Settings()
    assert settings.job_consumer_ack_wait_seconds == 150.0


def test_settings_normalizes_localhost_knowledge_interface_target() -> None:
    settings = Settings(KNOWLEDGE_INTERFACE_GRPC_TARGET="localhost:50051")
    assert settings.knowledge_interface_grpc_target == "127.0.0.1:50051"


def test_settings_leaves_non_localhost_knowledge_interface_target_unchanged() -> None:
    settings = Settings(KNOWLEDGE_INTERFACE_GRPC_TARGET="exobrain-knowledge-interface:50051")
    assert settings.knowledge_interface_grpc_target == "exobrain-knowledge-interface:50051"
