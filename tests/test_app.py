"""Tests for app.py - Main application."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestDisclaimerSettings:
    """Tests for disclaimer acceptance settings."""

    def test_is_disclaimer_accepted_default(self, temp_dir, monkeypatch):
        """Should return False when no settings exist."""
        monkeypatch.setattr("app.SETTINGS_DIR", temp_dir)
        monkeypatch.setattr("app.SETTINGS_FILE", temp_dir / "app_settings.json")

        from app import is_disclaimer_accepted

        assert is_disclaimer_accepted() is False

    def test_is_disclaimer_accepted_true(self, temp_dir, monkeypatch):
        """Should return True when disclaimer was accepted."""
        settings_file = temp_dir / "app_settings.json"
        with open(settings_file, "w") as f:
            json.dump({"disclaimer_accepted": True}, f)

        monkeypatch.setattr("app.SETTINGS_DIR", temp_dir)
        monkeypatch.setattr("app.SETTINGS_FILE", settings_file)

        from app import is_disclaimer_accepted

        assert is_disclaimer_accepted() is True

    def test_accept_disclaimer(self, temp_dir, monkeypatch):
        """Should save disclaimer acceptance."""
        settings_file = temp_dir / "app_settings.json"
        monkeypatch.setattr("app.SETTINGS_DIR", temp_dir)
        monkeypatch.setattr("app.SETTINGS_FILE", settings_file)

        from app import accept_disclaimer, is_disclaimer_accepted

        # Initially not accepted
        assert is_disclaimer_accepted() is False

        # Accept
        date = accept_disclaimer()

        # Should now be accepted
        assert is_disclaimer_accepted() is True
        assert date is not None
        assert len(date) > 0

    def test_get_disclaimer_date(self, temp_dir, monkeypatch):
        """Should return acceptance date."""
        settings_file = temp_dir / "app_settings.json"
        with open(settings_file, "w") as f:
            json.dump({
                "disclaimer_accepted": True,
                "disclaimer_accepted_date": "2024-01-15 10:30",
            }, f)

        monkeypatch.setattr("app.SETTINGS_DIR", temp_dir)
        monkeypatch.setattr("app.SETTINGS_FILE", settings_file)

        from app import get_disclaimer_date

        assert get_disclaimer_date() == "2024-01-15 10:30"

    def test_get_disclaimer_date_unknown(self, temp_dir, monkeypatch):
        """Should return 'Unknown' when no date stored."""
        monkeypatch.setattr("app.SETTINGS_DIR", temp_dir)
        monkeypatch.setattr("app.SETTINGS_FILE", temp_dir / "app_settings.json")

        from app import get_disclaimer_date

        assert get_disclaimer_date() == "Unknown"

    def test_settings_file_corrupted(self, temp_dir, monkeypatch):
        """Should handle corrupted settings file gracefully."""
        settings_file = temp_dir / "app_settings.json"
        with open(settings_file, "w") as f:
            f.write("not valid json {{{")

        monkeypatch.setattr("app.SETTINGS_DIR", temp_dir)
        monkeypatch.setattr("app.SETTINGS_FILE", settings_file)

        from app import is_disclaimer_accepted

        # Should return False (default) on error
        assert is_disclaimer_accepted() is False


class TestDetectRelease:
    """Tests for detect_release function."""

    def test_detect_release_from_env(self, monkeypatch):
        """Should use TOOLKIT_RELEASE environment variable."""
        monkeypatch.setenv("TOOLKIT_RELEASE", "minimal")

        from app import detect_release
        from core.config_manager import ConfigManager

        with patch.object(ConfigManager, "__init__", return_value=None):
            with patch.object(ConfigManager, "is_runpod", return_value=False):
                with patch.object(ConfigManager, "is_colab", return_value=False):
                    config = MagicMock()
                    config.is_runpod.return_value = False
                    config.is_colab.return_value = False

                    result = detect_release(config)

        assert result == "minimal"

    def test_detect_release_runpod(self, monkeypatch):
        """Should detect RunPod environment."""
        monkeypatch.delenv("TOOLKIT_RELEASE", raising=False)

        from app import detect_release

        config = MagicMock()
        config.is_runpod.return_value = True
        config.is_colab.return_value = False

        result = detect_release(config)
        assert result == "runpod"

    def test_detect_release_colab(self, monkeypatch):
        """Should detect Colab environment."""
        monkeypatch.delenv("TOOLKIT_RELEASE", raising=False)

        from app import detect_release

        config = MagicMock()
        config.is_runpod.return_value = False
        config.is_colab.return_value = True

        result = detect_release(config)
        assert result == "runpod"  # Colab uses runpod profile

    def test_detect_release_local(self, monkeypatch):
        """Should default to 'full' for local environment."""
        monkeypatch.delenv("TOOLKIT_RELEASE", raising=False)

        from app import detect_release

        config = MagicMock()
        config.is_runpod.return_value = False
        config.is_colab.return_value = False

        result = detect_release(config)
        assert result == "full"


class TestDiskInfo:
    """Tests for _get_disk_info function."""

    def test_get_disk_info_with_models_path(self, mock_comfyui_path):
        """Should show disk info for models path."""
        from app import _get_disk_info

        config = MagicMock()
        config.get_models_path.return_value = str(mock_comfyui_path / "models")
        config.is_runpod.return_value = False
        config.is_colab.return_value = False

        result = _get_disk_info(config)

        assert "Models" in result
        # Should show free/total
        assert "GB" in result or "MB" in result

    def test_get_disk_info_no_path(self):
        """Should handle missing models path."""
        from app import _get_disk_info

        config = MagicMock()
        config.get_models_path.return_value = None
        config.is_runpod.return_value = False
        config.is_colab.return_value = False

        result = _get_disk_info(config)

        assert "Not configured" in result

    def test_get_disk_info_runpod(self, temp_dir):
        """Should show RunPod-specific paths."""
        from app import _get_disk_info

        config = MagicMock()
        config.get_models_path.return_value = str(temp_dir)
        config.is_runpod.return_value = True
        config.is_colab.return_value = False

        with patch("os.path.exists", return_value=True):
            with patch("shutil.disk_usage") as mock_usage:
                mock_usage.return_value = MagicMock(
                    free=100 * 1024**3,
                    total=500 * 1024**3,
                    used=400 * 1024**3,
                )
                result = _get_disk_info(config)

        # Should mention workspace/volume for RunPod
        assert "Workspace" in result or "Volume" in result or "Models" in result


class TestDisclaimerText:
    """Tests for disclaimer content."""

    def test_disclaimer_text_exists(self):
        """DISCLAIMER_TEXT should be defined."""
        from app import DISCLAIMER_TEXT

        assert len(DISCLAIMER_TEXT) > 0

    def test_disclaimer_has_key_sections(self):
        """Disclaimer should contain key legal sections."""
        from app import DISCLAIMER_TEXT

        required_sections = [
            "Warranty",
            "Liability",
            "Copyright",
            "Third-Party",
            "Alpha",
            "Beta",
        ]

        for section in required_sections:
            assert section in DISCLAIMER_TEXT, f"Missing section: {section}"


class TestAppSettings:
    """Tests for app settings persistence."""

    def test_load_app_settings_empty(self, temp_dir, monkeypatch):
        """Should return empty dict when no settings file."""
        monkeypatch.setattr("app.SETTINGS_FILE", temp_dir / "nonexistent.json")

        from app import _load_app_settings

        result = _load_app_settings()
        assert result == {}

    def test_save_app_settings_creates_dir(self, temp_dir, monkeypatch):
        """Should create settings directory if needed."""
        settings_dir = temp_dir / "new_dir"
        settings_file = settings_dir / "settings.json"

        monkeypatch.setattr("app.SETTINGS_DIR", settings_dir)
        monkeypatch.setattr("app.SETTINGS_FILE", settings_file)

        from app import _save_app_settings

        _save_app_settings({"test": "value"})

        assert settings_dir.exists()
        assert settings_file.exists()

    def test_save_and_load_roundtrip(self, temp_dir, monkeypatch):
        """Should save and load settings correctly."""
        settings_dir = temp_dir / "config"
        settings_file = settings_dir / "settings.json"

        monkeypatch.setattr("app.SETTINGS_DIR", settings_dir)
        monkeypatch.setattr("app.SETTINGS_FILE", settings_file)

        from app import _save_app_settings, _load_app_settings

        original = {
            "key1": "value1",
            "key2": 123,
            "key3": True,
            "nested": {"a": 1, "b": 2},
        }

        _save_app_settings(original)
        loaded = _load_app_settings()

        assert loaded == original


class TestCreateApp:
    """Tests for create_app function."""

    def test_create_app_returns_blocks(self, temp_config_dir, monkeypatch):
        """create_app should return a Gradio Blocks object."""
        # This is a smoke test - full UI testing would require Gradio test utils

        # Mock the addon loader to avoid loading real addons
        with patch("app.AddonLoader") as MockLoader:
            mock_loader = MagicMock()
            mock_loader.load_release_config.return_value = {
                "name": "Test",
                "version": "1.0.0",
                "addons": [],
                "remote_profiles": {"enabled": False},
            }
            mock_loader.load_release.return_value = []
            MockLoader.return_value = mock_loader

            with patch("app.ConfigManager") as MockConfig:
                mock_config = MagicMock()
                mock_config.get_models_path.return_value = None
                mock_config.is_runpod.return_value = False
                mock_config.is_colab.return_value = False
                mock_config.get_environment.return_value = "local"
                mock_config.get_comfyui_path.return_value = None
                MockConfig.return_value = mock_config

                with patch("app.ProfileSyncService"):
                    with patch("app.is_disclaimer_accepted", return_value=True):
                        with patch("app.get_disclaimer_date", return_value="2024-01-01"):
                            from app import create_app

                            app = create_app("test")

                            # Check that app is a Gradio Blocks-like object
                            assert app is not None
                            assert hasattr(app, "launch")

    def test_create_app_handles_missing_release(self, temp_config_dir, monkeypatch):
        """Should fall back to minimal when release not found."""
        with patch("app.AddonLoader") as MockLoader:
            mock_loader = MagicMock()

            # First call raises, second succeeds (fallback)
            mock_loader.load_release_config.side_effect = [
                FileNotFoundError("Not found"),
                {"name": "Minimal", "version": "1.0.0", "addons": [], "remote_profiles": {"enabled": False}},
            ]
            mock_loader.load_release.return_value = []
            MockLoader.return_value = mock_loader

            with patch("app.ConfigManager") as MockConfig:
                mock_config = MagicMock()
                mock_config.get_models_path.return_value = None
                mock_config.is_runpod.return_value = False
                mock_config.is_colab.return_value = False
                mock_config.get_environment.return_value = "local"
                mock_config.get_comfyui_path.return_value = None
                MockConfig.return_value = mock_config

                with patch("app.ProfileSyncService"):
                    with patch("app.is_disclaimer_accepted", return_value=True):
                        with patch("app.get_disclaimer_date", return_value="2024-01-01"):
                            from app import create_app

                            # Should not raise
                            app = create_app("nonexistent")
                            assert app is not None
