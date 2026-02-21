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

    missing_package: list[str]
    message: str

    def __str__(self) -> str:
        """Return error message payload."""
        return f"Missing runtime dependencies for '{self.message}': {', '.join(self.missing_package)}"


@dataclass
class SchemaStoreError(PackageError):
    """Raised when schema loading/saving constraints are violated."""

    message: str

    def __str__(self) -> str:
        """Return error message payload."""
        return self.message


@dataclass(frozen=True)
class ModelMismatchError(PackageError):
    """Raised when the model used for an operation does not match the model of another operation."""

    provider1: str
    model1: str
    provider2: str
    model2: str

    def __str__(self) -> str:
        """Return error message payload."""
        return (
            f"Model mismatch: expected '{self.provider1}/{self.model1}', got '{self.provider2}/{self.model2}'"
        )
