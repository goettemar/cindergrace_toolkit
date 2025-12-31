"""Tests for core/ssl_utils.py - SSL security configuration."""

import json
import ssl
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestGetSSLContext:
    """Tests for get_ssl_context function."""

    def test_default_ssl_enabled(self, temp_dir):
        """SSL verification should be enabled by default."""
        from core.ssl_utils import get_ssl_context

        ctx = get_ssl_context(config_dir=temp_dir)

        # Default context should have verification enabled
        assert ctx.verify_mode == ssl.CERT_REQUIRED
        assert ctx.check_hostname is True

    def test_ssl_disabled_via_config(self, temp_config_dir):
        """SSL can be disabled via config.json security setting."""
        from core.ssl_utils import get_ssl_context

        # Create config with SSL disabled
        config_path = temp_config_dir["user_config"] / "config.json"
        with open(config_path, "w") as f:
            json.dump({"security": {"disable_ssl_verify": True}}, f)

        ctx = get_ssl_context(config_dir=temp_config_dir["root"])

        # Should have verification disabled
        assert ctx.verify_mode == ssl.CERT_NONE
        assert ctx.check_hostname is False

    def test_ssl_enabled_when_config_says_false(self, temp_config_dir):
        """SSL stays enabled when disable_ssl_verify is False."""
        from core.ssl_utils import get_ssl_context

        config_path = temp_config_dir["user_config"] / "config.json"
        with open(config_path, "w") as f:
            json.dump({"security": {"disable_ssl_verify": False}}, f)

        ctx = get_ssl_context(config_dir=temp_config_dir["root"])

        assert ctx.verify_mode == ssl.CERT_REQUIRED
        assert ctx.check_hostname is True

    def test_ssl_enabled_when_no_security_section(self, temp_config_dir):
        """SSL stays enabled when security section is missing."""
        from core.ssl_utils import get_ssl_context

        config_path = temp_config_dir["config"] / "config.json"
        with open(config_path, "w") as f:
            json.dump({"paths": {}}, f)

        ctx = get_ssl_context(config_dir=temp_config_dir["root"])

        assert ctx.verify_mode == ssl.CERT_REQUIRED

    def test_ssl_enabled_on_invalid_json(self, temp_config_dir):
        """SSL stays enabled when config.json is invalid."""
        from core.ssl_utils import get_ssl_context

        config_path = temp_config_dir["config"] / "config.json"
        with open(config_path, "w") as f:
            f.write("not valid json {{{")

        ctx = get_ssl_context(config_dir=temp_config_dir["root"])

        # Should default to secure
        assert ctx.verify_mode == ssl.CERT_REQUIRED

    def test_user_config_takes_priority(self, temp_config_dir):
        """User config (.config/) should override default config."""
        from core.ssl_utils import get_ssl_context

        # Default config says enabled
        default_config = temp_config_dir["config"] / "config.json"
        with open(default_config, "w") as f:
            json.dump({"security": {"disable_ssl_verify": False}}, f)

        # User config says disabled
        user_config = temp_config_dir["user_config"] / "config.json"
        with open(user_config, "w") as f:
            json.dump({"security": {"disable_ssl_verify": True}}, f)

        ctx = get_ssl_context(config_dir=temp_config_dir["root"])

        # User config should win - SSL disabled
        assert ctx.verify_mode == ssl.CERT_NONE

    def test_returns_ssl_context_type(self, temp_dir):
        """Should always return an ssl.SSLContext object."""
        from core.ssl_utils import get_ssl_context

        ctx = get_ssl_context(config_dir=temp_dir)

        assert isinstance(ctx, ssl.SSLContext)

    def test_default_context_when_no_config_dir(self):
        """Should work even when config_dir doesn't exist."""
        from core.ssl_utils import get_ssl_context

        # Use a path that doesn't exist
        ctx = get_ssl_context(config_dir=Path("/nonexistent/path"))

        # Should return secure default
        assert ctx.verify_mode == ssl.CERT_REQUIRED
