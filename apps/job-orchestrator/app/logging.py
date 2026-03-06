import logging
from typing import TextIO


def configure_logging(log_level: str, *, stream: TextIO | None = None, force: bool = False) -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=stream,
        force=force,
    )
