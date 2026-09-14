"""Shared pytest fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_env_file(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Prevent Settings from picking up the real project .env file.

    Settings.model_config uses a relative env_file=".env", which
    pydantic-settings resolves against the current working directory.
    Chdir into an empty tmp_path so tests only see variables set
    explicitly via monkeypatch, not whatever happens to be in the
    repo's real .env file.
    """
    monkeypatch.chdir(tmp_path)