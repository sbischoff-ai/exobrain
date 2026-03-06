from __future__ import annotations

import sys
from types import SimpleNamespace

from app.worker.jobs import knowledge_update


def test_configure_worker_logging_uses_stdout_and_force(monkeypatch) -> None:
    called: dict[str, object] = {}

    monkeypatch.setattr(knowledge_update, "get_settings", lambda: SimpleNamespace(effective_log_level="DEBUG"))

    def fake_configure_logging(log_level: str, *, stream=None, force: bool = False) -> None:
        called["log_level"] = log_level
        called["stream"] = stream
        called["force"] = force

    monkeypatch.setattr(knowledge_update, "configure_logging", fake_configure_logging)

    knowledge_update._configure_worker_logging()

    assert called == {
        "log_level": "DEBUG",
        "stream": sys.stdout,
        "force": True,
    }
