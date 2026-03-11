from app.settings import Settings
from app.config import load_models_config


def test_load_models_config_reads_aliases() -> None:
    config = load_models_config("config/models.yaml")

    assert "router" in config.aliases
    assert "coder" in config.aliases
    assert "all-purpose" in config.aliases
    assert config.aliases["router"].upstream_model == "gpt-5-nano"
    assert config.aliases["agent"].provider == "anthropic"
    assert config.aliases["reasoner"].defaults["reasoning_effort"] == "high"


def test_settings_defaults_provider_timeout() -> None:
    settings = Settings()
    assert settings.provider_timeout_seconds == 7200.0
