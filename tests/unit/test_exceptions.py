from extractforms.exceptions import (
    AsyncExecutionError,
    PackageError,
    SettingsError,
)


def test_root_exception_hierarchy() -> None:
    assert issubclass(SettingsError, PackageError)
    assert issubclass(AsyncExecutionError, PackageError)
