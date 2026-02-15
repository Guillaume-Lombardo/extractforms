from __future__ import annotations

from extractforms import logger as package_logger
from extractforms.logging import configure_logging, get_logger
from extractforms.settings import Settings


def test_stdlib_logger_is_configured(capsys) -> None:
    configure_logging(settings=Settings(log_json=False, log_level="INFO"), force=True)
    logger = get_logger("tests")
    logger.info("hello")

    captured = capsys.readouterr()
    assert "hello" in captured.err.lower()


def test_package_logger_created_on_import() -> None:
    assert callable(getattr(package_logger, "info", None))
