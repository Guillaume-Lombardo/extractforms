from __future__ import annotations

import pytest

from extractforms import cli
from extractforms.settings import Settings


def test_build_parser_supports_version_flag(capsys) -> None:
    parser = cli.build_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--version"])
    assert exc_info.value.code == 0

    captured = capsys.readouterr()
    assert "0.1.0" in captured.out


def test_main_initializes_logging_and_returns_zero(mocker) -> None:
    dummy_parser = mocker.Mock()
    dummy_parser.parse_args.return_value = None

    mocker.patch("extractforms.cli.build_parser", return_value=dummy_parser)
    mocker.patch("extractforms.cli.get_settings", return_value=Settings())
    mock_configure = mocker.patch("extractforms.cli.configure_logging")
    mock_logger = mocker.Mock()
    mocker.patch("extractforms.cli.get_logger", return_value=mock_logger)

    result = cli.main()

    assert result == 0
    mock_configure.assert_called_once()
    mock_logger.info.assert_called_once()
