"""Tests for core/config_manager.py - Configuration management."""

import json
import os
from pathlib import Path
from unittest.mock import patch


class TestConfigManager:
    """Tests for ConfigManager class."""

    def test_default_settings(self, temp_config_dir, monkeypatch):
        """Should have sensible default settings."""
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.PROJECT_DIR", temp_config_dir["root"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.CONFIG_DIR", temp_config_dir["config"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.USER_CONFIG_DIR", temp_config_dir["user_config"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.SETTINGS_FILE",
            temp_config_dir["config"] / "settings.json",
        )

        from core.config_manager import ConfigManager

        config = ConfigManager()

        assert config.get("download_parallel") == 2
        assert config.get("confirm_delete") is True
        assert config.get("show_file_sizes") is True

    def test_get_nonexistent_key_returns_default(self, temp_config_dir, monkeypatch):
        """Getting a non-existent key should return the provided default."""
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.PROJECT_DIR", temp_config_dir["root"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.CONFIG_DIR", temp_config_dir["config"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.USER_CONFIG_DIR", temp_config_dir["user_config"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.SETTINGS_FILE",
            temp_config_dir["config"] / "settings.json",
        )

        from core.config_manager import ConfigManager

        config = ConfigManager()

        assert config.get("nonexistent_key") is None
        assert config.get("nonexistent_key", "fallback") == "fallback"
        assert config.get("nonexistent_key", 42) == 42

    def test_set_and_get_value(self, temp_config_dir, monkeypatch):
        """Should be able to set and retrieve values."""
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.PROJECT_DIR", temp_config_dir["root"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.CONFIG_DIR", temp_config_dir["config"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.USER_CONFIG_DIR", temp_config_dir["user_config"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.SETTINGS_FILE",
            temp_config_dir["config"] / "settings.json",
        )

        from core.config_manager import ConfigManager

        config = ConfigManager()

        config.set("custom_key", "custom_value")
        assert config.get("custom_key") == "custom_value"

        config.set("number_key", 123)
        assert config.get("number_key") == 123

    def test_settings_persisted_to_file(self, temp_config_dir, monkeypatch):
        """Settings should be saved to file."""
        settings_file = temp_config_dir["config"] / "settings.json"
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.PROJECT_DIR", temp_config_dir["root"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.CONFIG_DIR", temp_config_dir["config"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.USER_CONFIG_DIR", temp_config_dir["user_config"]
        )
        monkeypatch.setattr("core.config_manager.ConfigManager.SETTINGS_FILE", settings_file)

        from core.config_manager import ConfigManager

        config = ConfigManager()
        config.set("test_key", "test_value")

        # Verify file was written
        assert settings_file.exists()
        with open(settings_file) as f:
            saved = json.load(f)
        assert saved.get("test_key") == "test_value"

    def test_get_all_returns_copy(self, temp_config_dir, monkeypatch):
        """get_all() should return a copy, not the original dict."""
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.PROJECT_DIR", temp_config_dir["root"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.CONFIG_DIR", temp_config_dir["config"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.USER_CONFIG_DIR", temp_config_dir["user_config"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.SETTINGS_FILE",
            temp_config_dir["config"] / "settings.json",
        )

        from core.config_manager import ConfigManager

        config = ConfigManager()

        all_settings = config.get_all()
        all_settings["modified_key"] = "should_not_affect_original"

        # Original should be unchanged
        assert config.get("modified_key") is None

    def test_reset_restores_defaults(self, temp_config_dir, monkeypatch):
        """reset() should restore default settings."""
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.PROJECT_DIR", temp_config_dir["root"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.CONFIG_DIR", temp_config_dir["config"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.USER_CONFIG_DIR", temp_config_dir["user_config"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.SETTINGS_FILE",
            temp_config_dir["config"] / "settings.json",
        )

        from core.config_manager import ConfigManager

        config = ConfigManager()

        config.set("custom_key", "custom_value")
        config.set("download_parallel", 99)

        config.reset()

        assert config.get("custom_key") is None
        assert config.get("download_parallel") == 2  # Default value


class TestEnvironmentDetection:
    """Tests for environment detection methods."""

    def test_is_local_by_default(self, temp_config_dir, monkeypatch):
        """Should detect local environment by default."""
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.PROJECT_DIR", temp_config_dir["root"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.CONFIG_DIR", temp_config_dir["config"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.USER_CONFIG_DIR", temp_config_dir["user_config"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.SETTINGS_FILE",
            temp_config_dir["config"] / "settings.json",
        )

        from core.config_manager import ConfigManager

        with patch("os.path.exists") as mock_exists:
            mock_exists.return_value = False

            config = ConfigManager()
            assert config.get_environment() == "local"
            assert config.is_runpod() is False
            assert config.is_colab() is False

    def test_detects_runpod(self, temp_config_dir, monkeypatch):
        """Should detect RunPod environment."""
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.PROJECT_DIR", temp_config_dir["root"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.CONFIG_DIR", temp_config_dir["config"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.USER_CONFIG_DIR", temp_config_dir["user_config"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.SETTINGS_FILE",
            temp_config_dir["config"] / "settings.json",
        )

        from core.config_manager import ConfigManager

        with patch("os.path.exists") as mock_exists:

            def exists_side_effect(path):
                return path in ["/workspace", "/runpod-volume"]

            mock_exists.side_effect = exists_side_effect

            config = ConfigManager()
            assert config.is_runpod() is True
            assert config.get_environment() == "runpod"

    def test_detects_colab(self, temp_config_dir, monkeypatch):
        """Should detect Google Colab environment."""
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.PROJECT_DIR", temp_config_dir["root"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.CONFIG_DIR", temp_config_dir["config"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.USER_CONFIG_DIR", temp_config_dir["user_config"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.SETTINGS_FILE",
            temp_config_dir["config"] / "settings.json",
        )

        from core.config_manager import ConfigManager

        with patch("os.path.exists") as mock_exists:

            def exists_side_effect(path):
                return path == "/content"

            mock_exists.side_effect = exists_side_effect

            with patch.dict(os.environ, {"COLAB_GPU": "1"}):
                config = ConfigManager()
                assert config.is_colab() is True
                assert config.get_environment() == "colab"


class TestComfyUIPathDetection:
    """Tests for ComfyUI path detection."""

    def test_get_comfyui_path_from_config(self, temp_config_dir, mock_comfyui_path, monkeypatch):
        """Should get ComfyUI path from config.json."""
        # Write config with path
        config_path = temp_config_dir["config"] / "config.json"
        with open(config_path, "w") as f:
            json.dump(
                {
                    "paths": {
                        "comfyui": {
                            "local": str(mock_comfyui_path),
                        }
                    }
                },
                f,
            )

        monkeypatch.setattr(
            "core.config_manager.ConfigManager.PROJECT_DIR", temp_config_dir["root"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.CONFIG_DIR", temp_config_dir["config"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.USER_CONFIG_DIR", temp_config_dir["user_config"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.SETTINGS_FILE",
            temp_config_dir["config"] / "settings.json",
        )

        from core.config_manager import ConfigManager

        with patch("os.path.exists") as mock_exists:

            def exists_side_effect(path):
                return path == str(mock_comfyui_path) or Path(path).exists()

            mock_exists.side_effect = exists_side_effect

            config = ConfigManager()
            result = config.get_comfyui_path()
            assert result == str(mock_comfyui_path)

    def test_get_models_path(self, temp_config_dir, mock_comfyui_path, monkeypatch):
        """Should get models path from ComfyUI path."""
        config_path = temp_config_dir["config"] / "config.json"
        with open(config_path, "w") as f:
            json.dump(
                {
                    "paths": {
                        "comfyui": {
                            "local": str(mock_comfyui_path),
                        }
                    }
                },
                f,
            )

        monkeypatch.setattr(
            "core.config_manager.ConfigManager.PROJECT_DIR", temp_config_dir["root"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.CONFIG_DIR", temp_config_dir["config"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.USER_CONFIG_DIR", temp_config_dir["user_config"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.SETTINGS_FILE",
            temp_config_dir["config"] / "settings.json",
        )

        from core.config_manager import ConfigManager

        config = ConfigManager()
        result = config.get_models_path()

        # Result should be the models subdirectory of the mock ComfyUI path
        assert result is not None
        assert result.endswith("models")
        assert "ComfyUI" in result

    def test_get_comfyui_path_returns_none_when_not_found(self, temp_config_dir, monkeypatch):
        """Should return None when ComfyUI is not found."""
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.PROJECT_DIR", temp_config_dir["root"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.CONFIG_DIR", temp_config_dir["config"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.USER_CONFIG_DIR", temp_config_dir["user_config"]
        )
        monkeypatch.setattr(
            "core.config_manager.ConfigManager.SETTINGS_FILE",
            temp_config_dir["config"] / "settings.json",
        )

        from core.config_manager import ConfigManager

        with patch("os.path.exists", return_value=False):
            with patch("pathlib.Path.exists", return_value=False):
                config = ConfigManager()
                assert config.get_comfyui_path() is None
                assert config.get_models_path() is None
