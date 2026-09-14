# conftest.py
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_env_file(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Prevent Settings from picking up real environment/`.env` values.

    - chdir hides the repo's real .env file (relative env_file=".env"
      resolves against cwd).
    - delenv scrubs any of the same variables that are set directly in
      the OS environment, which chdir cannot touch.
    """
    monkeypatch.chdir(tmp_path)

    for var in (
        "AIBI_ENVIRONMENT",
        "AIBI_DB_HOST",
        "AIBI_DB_PORT",
        "AIBI_DB_NAME",
        "AIBI_DB_USER",
        "AIBI_DB_PASSWORD",
        "AIBI_DB_ECHO",
        "AIBI_DB_POOL_SIZE",
        "AIBI_DB_MAX_OVERFLOW",
        "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)