from __future__ import annotations

from app.core.settings import Settings


def test_settings_do_not_include_legacy_nats_enqueue_configuration() -> None:
    settings = Settings()

    assert not hasattr(settings, "exobrain_nats_url")
    assert not hasattr(settings, "job_queue_subject")


def test_settings_include_knowledge_interface_grpc_configuration() -> None:
    settings = Settings()

    assert settings.knowledge_interface_grpc_target == "localhost:50051"
    assert settings.knowledge_interface_connect_timeout_seconds == 5.0


def test_settings_model_provider_base_url_defaults_to_v1() -> None:
    settings = Settings()

    assert settings.model_provider_base_url == "http://localhost:8010/v1"


def test_settings_model_provider_base_url_normalizes_missing_v1() -> None:
    settings = Settings(MODEL_PROVIDER_BASE_URL="http://localhost:8010")

    assert settings.model_provider_base_url == "http://localhost:8010/v1"


def test_settings_include_mcp_configuration() -> None:
    settings = Settings()

    assert settings.mcp_server_url == "http://localhost:8090"
    assert settings.mcp_request_timeout_seconds == 5.0
    assert settings.mcp_max_retries == 2
