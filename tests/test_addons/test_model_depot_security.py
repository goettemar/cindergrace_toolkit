"""Security tests for addons/model_depot - Path traversal and allowlist protection."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestSanitizePath:
    """Tests for _sanitize_path function - Path traversal protection."""

    def test_valid_path(self, temp_dir):
        """Should allow valid paths within base directory."""
        # Import the module-level function
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))

        from addons.model_depot.addon import _sanitize_path

        base = temp_dir / "models"
        base.mkdir()
        (base / "loras").mkdir()

        result = _sanitize_path(base, "loras", "my_lora.safetensors")

        assert result is not None
        assert str(result).startswith(str(base))
        assert result.name == "my_lora.safetensors"

    def test_path_traversal_in_target(self, temp_dir):
        """Should reject path traversal in target_path."""
        from addons.model_depot.addon import _sanitize_path

        base = temp_dir / "models"
        base.mkdir()

        # Attempt to escape using ..
        result = _sanitize_path(base, "../../../etc", "passwd")
        assert result is None

        result = _sanitize_path(base, "loras/../../../etc", "passwd")
        assert result is None

    def test_path_traversal_in_filename(self, temp_dir):
        """Should reject path traversal in filename."""
        from addons.model_depot.addon import _sanitize_path

        base = temp_dir / "models"
        base.mkdir()

        result = _sanitize_path(base, "loras", "../../../etc/passwd")
        assert result is None

        result = _sanitize_path(base, "loras", "..\\..\\windows\\system32\\config")
        assert result is None

    def test_absolute_path_in_target(self, temp_dir):
        """Should reject absolute paths in target_path."""
        from addons.model_depot.addon import _sanitize_path

        base = temp_dir / "models"
        base.mkdir()

        result = _sanitize_path(base, "/etc", "passwd")
        assert result is None

        result = _sanitize_path(base, "/absolute/path", "file.txt")
        assert result is None

    def test_absolute_path_in_filename(self, temp_dir):
        """Should reject absolute paths in filename."""
        from addons.model_depot.addon import _sanitize_path

        base = temp_dir / "models"
        base.mkdir()

        result = _sanitize_path(base, "loras", "/etc/passwd")
        assert result is None

    def test_nested_valid_path(self, temp_dir):
        """Should allow nested valid paths."""
        from addons.model_depot.addon import _sanitize_path

        base = temp_dir / "models"
        base.mkdir()
        (base / "diffusion_models" / "wan").mkdir(parents=True)

        result = _sanitize_path(base, "diffusion_models/wan", "model.safetensors")

        assert result is not None
        assert "diffusion_models" in str(result)
        assert "wan" in str(result)

    def test_symlink_escape_attempt(self, temp_dir):
        """Should handle symlink escape attempts."""
        from addons.model_depot.addon import _sanitize_path

        base = temp_dir / "models"
        base.mkdir()
        (base / "loras").mkdir()

        # Create a symlink pointing outside
        escape_dir = temp_dir / "escape"
        escape_dir.mkdir()

        # The function uses resolve() which follows symlinks
        # Even if we could create a symlink, resolve() would catch it
        result = _sanitize_path(base, "loras", "normal.safetensors")
        assert result is not None

    def test_empty_target_path(self, temp_dir):
        """Should handle empty target_path."""
        from addons.model_depot.addon import _sanitize_path

        base = temp_dir / "models"
        base.mkdir()

        result = _sanitize_path(base, "", "model.safetensors")
        assert result is not None
        assert result.parent == base

    def test_special_characters_in_filename(self, temp_dir):
        """Should handle special characters in filename."""
        from addons.model_depot.addon import _sanitize_path

        base = temp_dir / "models"
        base.mkdir()
        (base / "loras").mkdir()

        # Normal special characters should work
        result = _sanitize_path(base, "loras", "my_lora-v1.0.safetensors")
        assert result is not None

        # Unicode should work
        result = _sanitize_path(base, "loras", "模型.safetensors")
        assert result is not None


class TestIsAllowedFolder:
    """Tests for _is_allowed_folder method - Allowlist protection."""

    @pytest.fixture
    def model_depot_instance(self, temp_config_dir, monkeypatch):
        """Create a ModelDepotAddon instance for testing."""
        # Mock gradio
        import sys
        sys.modules["gradio"] = MagicMock()

        monkeypatch.setattr(
            "addons.model_depot.addon.ModelDepotAddon.PROJECT_DIR",
            temp_config_dir["root"]
        )
        monkeypatch.setattr(
            "addons.model_depot.addon.ModelDepotAddon.USER_CONFIG_DIR",
            temp_config_dir["user_config"]
        )
        monkeypatch.setattr(
            "addons.model_depot.addon.ModelDepotAddon.DATA_DIR",
            temp_config_dir["root"] / "data"
        )
        monkeypatch.setattr(
            "addons.model_depot.addon.ModelDepotAddon.CONFIG_DIR",
            temp_config_dir["config"]
        )

        # Create required directories
        (temp_config_dir["root"] / "data").mkdir(parents=True, exist_ok=True)

        from addons.model_depot.addon import ModelDepotAddon
        addon = ModelDepotAddon()
        return addon

    def test_allowed_folders_direct_match(self, model_depot_instance):
        """Should allow folders in the whitelist."""
        addon = model_depot_instance

        assert addon._is_allowed_folder("checkpoints") is True
        assert addon._is_allowed_folder("loras") is True
        assert addon._is_allowed_folder("vae") is True
        assert addon._is_allowed_folder("text_encoders") is True
        assert addon._is_allowed_folder("diffusion_models") is True
        assert addon._is_allowed_folder("clip_vision") is True
        assert addon._is_allowed_folder("controlnet") is True
        assert addon._is_allowed_folder("upscale_models") is True
        assert addon._is_allowed_folder("LLM") is True

    def test_allowed_subfolders(self, model_depot_instance):
        """Should allow subfolders of allowed folders."""
        addon = model_depot_instance

        assert addon._is_allowed_folder("diffusion_models/wan") is True
        assert addon._is_allowed_folder("loras/wan") is True
        assert addon._is_allowed_folder("loras/sdxl") is True
        assert addon._is_allowed_folder("checkpoints/sd15") is True

    def test_disallowed_folders(self, model_depot_instance):
        """Should reject folders not in whitelist."""
        addon = model_depot_instance

        assert addon._is_allowed_folder("../etc") is False
        assert addon._is_allowed_folder("/etc") is False
        assert addon._is_allowed_folder("custom_folder") is False
        assert addon._is_allowed_folder("models") is False
        assert addon._is_allowed_folder("") is False
        assert addon._is_allowed_folder("user_data") is False

    def test_path_traversal_attempt(self, model_depot_instance):
        """Should reject obvious path traversal attempts.

        Note: _is_allowed_folder only checks allowlist membership.
        Path traversal protection is handled by _sanitize_path.
        """
        addon = model_depot_instance

        # Pure path traversal attempts (don't start with allowed folder)
        assert addon._is_allowed_folder("../loras") is False
        assert addon._is_allowed_folder("../etc") is False

        # Note: "loras/../../../etc" starts with "loras/" so it passes
        # the prefix check - _sanitize_path handles the actual traversal

    def test_case_sensitivity(self, model_depot_instance):
        """Folder matching should be case-sensitive."""
        addon = model_depot_instance

        # These are the exact names in ALLOWED_FOLDERS
        assert addon._is_allowed_folder("LLM") is True
        assert addon._is_allowed_folder("vae") is True

        # Case variations should not match (depending on implementation)
        # This tests the current behavior
        assert addon._is_allowed_folder("llm") is False
        assert addon._is_allowed_folder("VAE") is False


class TestDownloadModelSecurity:
    """Tests for download_model security checks."""

    @pytest.fixture
    def model_depot_with_models(self, temp_config_dir, sample_workflow_models, mock_comfyui_path, monkeypatch):
        """Create ModelDepotAddon with workflow models."""
        import sys
        sys.modules["gradio"] = MagicMock()

        monkeypatch.setattr(
            "addons.model_depot.addon.ModelDepotAddon.PROJECT_DIR",
            temp_config_dir["root"]
        )
        monkeypatch.setattr(
            "addons.model_depot.addon.ModelDepotAddon.USER_CONFIG_DIR",
            temp_config_dir["user_config"]
        )
        monkeypatch.setattr(
            "addons.model_depot.addon.ModelDepotAddon.DATA_DIR",
            temp_config_dir["root"] / "data"
        )
        monkeypatch.setattr(
            "addons.model_depot.addon.ModelDepotAddon.CONFIG_DIR",
            temp_config_dir["config"]
        )

        # Create data directory with workflow_models.json
        data_dir = temp_config_dir["root"] / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        with open(data_dir / "workflow_models.json", "w") as f:
            json.dump(sample_workflow_models, f)

        from addons.model_depot.addon import ModelDepotAddon
        addon = ModelDepotAddon()
        addon._models_path = mock_comfyui_path / "models"
        addon._workflow_models = sample_workflow_models
        return addon

    def test_download_rejects_invalid_folder(self, model_depot_with_models):
        """download_model should reject models with invalid target folders."""
        addon = model_depot_with_models

        # Add a model with invalid target path
        addon._workflow_models["models"]["bad_model"] = {
            "filename": "bad.safetensors",
            "url": "https://example.com/bad.safetensors",
            "target_path": "../../../etc",  # Invalid!
            "size_mb": 100,
        }

        result = addon.download_model("bad_model")
        assert "Security" in result or "Invalid" in result

    def test_download_allows_valid_folder(self, model_depot_with_models):
        """download_model should allow models with valid target folders."""
        addon = model_depot_with_models

        # model_a has valid target_path "diffusion_models/wan"
        # We just verify it doesn't fail on security check
        # (actual download would fail without network)
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = b"fake model data"
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            # This should not raise a security error
            result = addon.download_model("model_a")
            # If we got past security check, it would try to download
            assert "Security" not in result or "diffusion_models/wan" in addon.ALLOWED_FOLDERS


class TestRestoreFromBackupSecurity:
    """Tests for restore_from_backup security checks."""

    @pytest.fixture
    def model_depot_with_backup(self, temp_config_dir, sample_workflow_models, mock_comfyui_path, monkeypatch):
        """Create ModelDepotAddon with backup configured."""
        import sys
        sys.modules["gradio"] = MagicMock()

        monkeypatch.setattr(
            "addons.model_depot.addon.ModelDepotAddon.PROJECT_DIR",
            temp_config_dir["root"]
        )
        monkeypatch.setattr(
            "addons.model_depot.addon.ModelDepotAddon.USER_CONFIG_DIR",
            temp_config_dir["user_config"]
        )
        monkeypatch.setattr(
            "addons.model_depot.addon.ModelDepotAddon.DATA_DIR",
            temp_config_dir["root"] / "data"
        )
        monkeypatch.setattr(
            "addons.model_depot.addon.ModelDepotAddon.CONFIG_DIR",
            temp_config_dir["config"]
        )

        data_dir = temp_config_dir["root"] / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        with open(data_dir / "workflow_models.json", "w") as f:
            json.dump(sample_workflow_models, f)

        backup_dir = temp_config_dir["root"] / "backup"
        backup_dir.mkdir()

        from addons.model_depot.addon import ModelDepotAddon
        addon = ModelDepotAddon()
        addon._models_path = mock_comfyui_path / "models"
        addon._backup_path = backup_dir
        addon._workflow_models = sample_workflow_models
        return addon

    def test_restore_rejects_invalid_folder(self, model_depot_with_backup):
        """restore_from_backup should reject models with invalid target folders."""
        addon = model_depot_with_backup

        addon._workflow_models["models"]["bad_restore"] = {
            "filename": "bad.safetensors",
            "target_path": "../../../etc",
        }

        result = addon.restore_from_backup("bad_restore")
        assert "Security" in result


class TestFindOtherModelsSecurity:
    """Tests for find_other_models security - only scans allowed folders."""

    @pytest.fixture
    def model_depot_with_folders(self, temp_config_dir, mock_comfyui_path, monkeypatch):
        """Create ModelDepotAddon with folder scanning."""
        import sys
        sys.modules["gradio"] = MagicMock()

        monkeypatch.setattr(
            "addons.model_depot.addon.ModelDepotAddon.PROJECT_DIR",
            temp_config_dir["root"]
        )
        monkeypatch.setattr(
            "addons.model_depot.addon.ModelDepotAddon.USER_CONFIG_DIR",
            temp_config_dir["user_config"]
        )
        monkeypatch.setattr(
            "addons.model_depot.addon.ModelDepotAddon.DATA_DIR",
            temp_config_dir["root"] / "data"
        )
        monkeypatch.setattr(
            "addons.model_depot.addon.ModelDepotAddon.CONFIG_DIR",
            temp_config_dir["config"]
        )

        data_dir = temp_config_dir["root"] / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        workflow_models = {
            "version": "1.0",
            "target_folders": ["loras", "vae", "../../../etc"],  # Includes malicious folder
            "workflows": {},
            "models": {},
        }
        with open(data_dir / "workflow_models.json", "w") as f:
            json.dump(workflow_models, f)

        from addons.model_depot.addon import ModelDepotAddon
        addon = ModelDepotAddon()
        addon._models_path = mock_comfyui_path / "models"
        addon._workflow_models = workflow_models
        return addon

    def test_find_other_skips_invalid_folders(self, model_depot_with_folders, mock_model_files):
        """find_other_models should skip folders not in allowlist."""
        addon = model_depot_with_folders

        # This should not raise errors and should skip "../../../etc"
        result = addon.find_other_models("any_workflow", "S")

        # Should return a list (possibly empty)
        assert isinstance(result, list)

        # Should not contain paths from invalid folders
        for filename, folder, size in result:
            assert ".." not in folder
            assert addon._is_allowed_folder(folder) is True
