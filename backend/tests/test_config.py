"""
Tests for Application Settings and Configuration validation.
"""
import pytest
from app.core.config import Settings


def test_settings_default_values():
    """Verify default settings loaded correctly."""
    settings = Settings()
    assert settings.APP_NAME == "FinBridge"
    assert settings.ENVIRONMENT in {"development", "staging", "production", "test"}
    assert settings.PORT == 8000
    assert len(settings.cors_origins) >= 1


def test_settings_cors_origins_parsing():
    """Verify parsing comma-separated origins."""
    settings = Settings(ALLOWED_ORIGINS="http://localhost:3000, https://app.finbridge.io")
    origins = settings.cors_origins
    assert "http://localhost:3000" in origins
    assert "https://app.finbridge.io" in origins


def test_invalid_environment_raises_validation_error():
    """Verify invalid environment string raises ValueError."""
    with pytest.raises(Exception):
        Settings(ENVIRONMENT="invalid_env_name")
