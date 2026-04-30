"""Smoke test verifying the regulaitor package imports and exposes a version."""

from regulaitor import __version__


def test_version_is_defined() -> None:
    assert __version__
    assert isinstance(__version__, str)


def test_version_is_semver_like() -> None:
    parts = __version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)
