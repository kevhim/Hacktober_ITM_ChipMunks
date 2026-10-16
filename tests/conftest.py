"""Tests may use local stubs, but must never consume developer cloud credentials."""

import pytest


@pytest.fixture(autouse=True)
def offline_credentials(monkeypatch):
    for key in (
        "GEMINI_API_KEY", "OPTIONAL_CLOUD_ENDPOINT", "OPTIONAL_CLOUD_KEY",
        "TARGET_ENDPOINT", "TARGET_API_KEY", "TARGET_MODEL",
    ):
        monkeypatch.setenv(key, "")
