"""Package exceptions."""

from __future__ import annotations

from dataclasses import dataclass


class PackageError(Exception):
    """Root exception for the package."""


@dataclass(frozen=True)
class SettingsError(PackageError):
    """Raised when settings cannot be loaded or validated."""

    message: str = "Failed to load settings"
    exc: BaseException | None = None

    def __str__(self) -> str:
        """Return error message payload."""
        return f"{self.message}: {self.exc}" if self.exc else self.message


@dataclass(frozen=True)
class AsyncExecutionError(PackageError):
    """Raised when an async operation fails in compatibility runner."""

    result: BaseException
    message: str = "Async operation failed"

    def __str__(self) -> str:
        """Return error message payload."""
        return f"{self.message}: {self.result}"
