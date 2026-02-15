"""Project enums."""

from __future__ import annotations

from enum import StrEnum


class _EnumMixin(StrEnum):
    """Shared conversion helpers for user-facing enums."""

    @classmethod
    def from_str(cls, value: str) -> _EnumMixin:
        """Parse enum from string.

        Args:
            value: Raw string value.

        Raises:
            ValueError: If the value is not supported.

        Returns:
            _EnumMixin: Parsed enum value.
        """
        try:
            return cls(value)
        except ValueError as exc:
            supported = ", ".join(member.value for member in cls)
            message = f"Unsupported {cls.__name__} value '{value}'. Expected one of: {supported}"
            raise ValueError(message) from exc

    def to_str(self) -> str:
        """Return string representation.

        Returns:
            str: Enum string value.
        """
        return self.value


class PassMode(_EnumMixin):
    """Extraction pass strategy."""

    ONE_PASS = "one_pass"  # noqa: S105
    TWO_PASS = "two_pass"  # noqa: S105
    ONE_SCHEMA_PASS = "one_schema_pass"  # noqa: S105


class FieldKind(_EnumMixin):
    """Supported schema field kinds."""

    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    CHECKBOX = "checkbox"
    SELECT = "select"
    UNKNOWN = "unknown"


class ConfidenceLevel(_EnumMixin):
    """Confidence level for a single extracted value."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"
