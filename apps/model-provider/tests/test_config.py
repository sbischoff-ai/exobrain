from app.config import load_models_config


def test_load_models_config_reads_aliases() -> None:
    config = load_models_config("config/models.yaml")

    assert "router" in config.aliases
    assert "all-purpose" in config.aliases
    assert config.aliases["agent"].provider == "openai"
