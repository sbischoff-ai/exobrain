import logging


def configure_logging(log_level: str) -> None:
    """Configure process-wide logging for backend services."""

    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
