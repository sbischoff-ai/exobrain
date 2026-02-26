from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class AliasConfig:
    alias: str
    provider: str
    upstream_model: str
    mode: str
    defaults: dict[str, Any]


@dataclass(frozen=True)
class ModelsConfig:
    aliases: dict[str, AliasConfig]


def load_models_config(config_path: str) -> ModelsConfig:
    parsed = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    if not isinstance(parsed, dict) or "aliases" not in parsed:
        raise ValueError("models config must contain an aliases map")

    aliases: dict[str, AliasConfig] = {}
    raw_aliases = parsed["aliases"]
    if not isinstance(raw_aliases, dict):
        raise ValueError("aliases must be a map")

    for alias, payload in raw_aliases.items():
        if not isinstance(payload, dict):
            raise ValueError(f"alias {alias} must be a map")
        provider = str(payload.get("provider", "")).strip()
        upstream_model = str(payload.get("upstream_model", "")).strip()
        mode = str(payload.get("mode", "")).strip()
        defaults = payload.get("defaults", {}) or {}
        if not provider or not upstream_model or mode not in {"chat", "embeddings"}:
            raise ValueError(f"alias {alias} missing required provider/upstream_model/mode")
        aliases[alias] = AliasConfig(
            alias=alias,
            provider=provider,
            upstream_model=upstream_model,
            mode=mode,
            defaults=defaults,
        )
    return ModelsConfig(aliases=aliases)
