from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from extractforms import cli
from extractforms.typing.enums import PassMode
from extractforms.settings import Settings


def test_build_parser_supports_version_flag(capsys) -> None:
    parser = cli.build_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--version"])
    assert exc_info.value.code == 0

    captured = capsys.readouterr()
    assert "0.1.0" in captured.out


def test_extract_request_uses_one_schema_mode_when_schema_is_provided() -> None:
    args = Namespace(
        input_path=Path("input.pdf"),
        output_path=Path("out.json"),
        mode=PassMode.TWO_PASS,
        no_cache=False,
        dpi=150,
        image_format="png",
        page_start=None,
        page_end=None,
        max_pages=None,
        chunk_pages=1,
        schema_id="abc",
        schema_path=None,
        match_schema=False,
        extra_instructions=None,
    )

    request = cli._build_extract_request(args)
    assert request.mode == PassMode.ONE_SCHEMA_PASS


def test_main_runs_extract_flow(mocker, tmp_path: Path) -> None:
    output_path = tmp_path / "result.json"

    parser = mocker.Mock()
    parser.parse_args.return_value = Namespace(
        command="extract",
        input_path=Path("input.pdf"),
        output_path=output_path,
        mode=PassMode.TWO_PASS,
        no_cache=False,
        dpi=200,
        image_format="png",
        page_start=None,
        page_end=None,
        max_pages=None,
        chunk_pages=1,
        schema_id=None,
        schema_path=None,
        match_schema=False,
        extra_instructions=None,
    )

    mocker.patch("extractforms.cli.build_parser", return_value=parser)
    mocker.patch("extractforms.cli.get_settings", return_value=Settings())
    mocker.patch("extractforms.cli.ensure_cli_dependencies_for_extract")
    mocker.patch("extractforms.cli.run_extract")
    mock_persist = mocker.patch("extractforms.cli.persist_result")

    result = cli.main()

    assert result == 0
    mock_persist.assert_called_once()
