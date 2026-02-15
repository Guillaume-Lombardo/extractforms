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


@dataclass(frozen=True)
class BackendError(PackageError):
    """Raised when a backend call fails."""

    message: str

    def __str__(self) -> str:
        """Return error message payload."""
        return self.message


@dataclass(frozen=True)
class ExtractionError(PackageError):
    """Raised when extraction orchestration fails."""

    message: str

    def __str__(self) -> str:
        """Return error message payload."""
        return self.message


@dataclass(frozen=True)
class DependencyError(PackageError):
    """Raised when optional runtime dependencies are missing."""

    message: str

    def __str__(self) -> str:
        """Return error message payload."""
        return self.message
