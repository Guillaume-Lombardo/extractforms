"""CLI entry point for ExtractForms."""

from __future__ import annotations

import argparse
from pathlib import Path

from extractforms import __version__, logger
from extractforms.dependencies import ensure_cli_dependencies_for_extract
from extractforms.exceptions import PackageError
from extractforms.extractor import persist_result, run_extract
from extractforms.logging import configure_logging
from extractforms.settings import get_settings
from extractforms.typing.enums import PassMode
from extractforms.typing.models import ExtractRequest


def _pass_mode_from_cli(value: str) -> PassMode:
    """Convert `--passes` CLI value into pass mode.

    Args:
        value (str): CLI value (`1` or `2`).

    Raises:
        argparse.ArgumentTypeError: If value is not supported.

    Returns:
        PassMode: Selected pass mode.
    """
    mapping = {
        "1": PassMode.ONE_PASS,
        "2": PassMode.TWO_PASS,
    }
    if value not in mapping:
        raise argparse.ArgumentTypeError("--passes must be one of: 1, 2")  # noqa: TRY003
    return mapping[value]


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser.

    Returns:
        argparse.ArgumentParser: The configured argument parser.
    """
    parser = argparse.ArgumentParser(prog="extractforms")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    extract_parser = subparsers.add_parser("extract", help="Extract key/value fields from a PDF form")
    extract_parser.add_argument("--input", required=True, type=Path, dest="input_path")
    extract_parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/result.json"),
        dest="output_path",
    )
    extract_parser.add_argument("--passes", default="2", type=_pass_mode_from_cli, dest="mode")
    extract_parser.add_argument("--no-cache", action="store_true", dest="no_cache")

    extract_parser.add_argument("--dpi", type=int, default=200)
    extract_parser.add_argument("--image-format", default="png", dest="image_format")
    extract_parser.add_argument("--page-start", type=int, default=None, dest="page_start")
    extract_parser.add_argument("--page-end", type=int, default=None, dest="page_end")
    extract_parser.add_argument("--max-pages", type=int, default=None, dest="max_pages")

    extract_parser.add_argument("--chunk-pages", type=int, default=1, dest="chunk_pages")
    extract_parser.add_argument("--drop-blank-pages", action="store_true", dest="drop_blank_pages")
    extract_parser.add_argument(
        "--blank-page-ink-threshold",
        type=float,
        default=None,
        dest="blank_page_ink_threshold",
    )
    extract_parser.add_argument(
        "--blank-page-near-white-level",
        type=int,
        default=None,
        dest="blank_page_near_white_level",
    )
    extract_parser.add_argument("--extra-instructions", default=None, dest="extra_instructions")

    extract_parser.add_argument("--schema-id", default=None, dest="schema_id")
    extract_parser.add_argument("--schema-path", type=Path, default=None, dest="schema_path")
    extract_parser.add_argument("--match-schema", action="store_true", dest="match_schema")

    return parser


def _build_extract_request(args: argparse.Namespace) -> ExtractRequest:
    """Build extraction request from CLI arguments.

    Args:
        args (argparse.Namespace): Parsed CLI args.

    Returns:
        ExtractRequest: Request object.
    """
    mode = args.mode
    if args.schema_id or args.schema_path:
        mode = PassMode.ONE_SCHEMA_PASS

    return ExtractRequest(
        input_path=args.input_path,
        output_path=args.output_path,
        mode=mode,
        use_cache=not args.no_cache,
        dpi=args.dpi,
        image_format=args.image_format,
        page_start=args.page_start,
        page_end=args.page_end,
        max_pages=args.max_pages,
        chunk_pages=args.chunk_pages,
        drop_blank_pages=getattr(args, "drop_blank_pages", False),
        blank_page_ink_threshold=getattr(args, "blank_page_ink_threshold", None),
        blank_page_near_white_level=getattr(args, "blank_page_near_white_level", None),
        schema_id=args.schema_id,
        schema_path=args.schema_path,
        match_schema=args.match_schema,
        extra_instructions=args.extra_instructions,
    )


def main() -> int:
    """Run the CLI.

    Returns:
        int: Exit code (0 for success, 1 for error).
    """
    settings = get_settings()
    configure_logging(settings=settings)

    parser = build_parser()
    args = parser.parse_args()

    if args.command != "extract":
        parser.print_help()
        return 0

    ensure_cli_dependencies_for_extract()
    request = _build_extract_request(args)

    try:
        result = run_extract(request, settings)
    except PackageError:
        logger.exception("Extraction failed")
        return 1
    except KeyboardInterrupt:
        logger.info("Extraction aborted by user")
        return 130
    except Exception:
        logger.exception("Unexpected error during extraction")
        return 1
    finally:
        settings.close_httpx_clients()

    output_path = request.output_path
    if output_path is None:
        output_path = Path("results/result.json")
    persist_result(result, output_path)
    logger.info("Extraction completed", extra={"output_path": str(output_path)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
