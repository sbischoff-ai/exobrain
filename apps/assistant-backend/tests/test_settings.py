from __future__ import annotations

from app.core.settings import Settings


def test_settings_do_not_include_legacy_nats_enqueue_configuration() -> None:
    settings = Settings()

    assert not hasattr(settings, "exobrain_nats_url")
    assert not hasattr(settings, "job_queue_subject")
