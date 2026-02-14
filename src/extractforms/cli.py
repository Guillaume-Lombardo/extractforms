"""CLI entry point for ExtractForms."""

from __future__ import annotations

import argparse

from extractforms import __version__
from extractforms.logging import configure_logging, get_logger
from extractforms.settings import get_settings


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser.

    Returns:
        argparse.ArgumentParser: The configured argument parser.
    """
    parser = argparse.ArgumentParser(prog="extractforms")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main() -> int:
    """Run the CLI.

    Returns:
        int: Exit code (0 for success).
    """
    parser = build_parser()
    parser.parse_args()
    configure_logging(settings=get_settings())
    logger = get_logger("extractforms.cli")
    logger.info("CLI initialized", version=__version__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
