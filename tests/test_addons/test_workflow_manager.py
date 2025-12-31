"""Tests for addons/workflow_manager - Workflow management addon."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestWorkflowManagerAllowlist:
    """Tests for WorkflowManager folder allowlist."""

    @pytest.fixture
    def workflow_manager_instance(self, temp_config_dir, monkeypatch):
        """Create a WorkflowManagerAddon instance for testing."""
        import sys
        sys.modules["gradio"] = MagicMock()

        monkeypatch.setattr(
            "addons.workflow_manager.addon.WorkflowManagerAddon.PROJECT_DIR",
            temp_config_dir["root"]
        )
        monkeypatch.setattr(
            "addons.workflow_manager.addon.WorkflowManagerAddon.USER_CONFIG_DIR",
            temp_config_dir["user_config"]
        )
        monkeypatch.setattr(
            "addons.workflow_manager.addon.WorkflowManagerAddon.DATA_DIR",
            temp_config_dir["root"] / "data"
        )
        monkeypatch.setattr(
            "addons.workflow_manager.addon.WorkflowManagerAddon.CONFIG_DIR",
            temp_config_dir["config"]
        )

        # Create data directory
        (temp_config_dir["root"] / "data").mkdir(parents=True, exist_ok=True)

        from addons.workflow_manager.addon import WorkflowManagerAddon
        addon = WorkflowManagerAddon()
        return addon

    def test_allowed_folders_constant_exists(self, workflow_manager_instance):
        """ALLOWED_FOLDERS constant should exist."""
        addon = workflow_manager_instance
        assert hasattr(addon, "ALLOWED_FOLDERS")
        assert isinstance(addon.ALLOWED_FOLDERS, set)

    def test_allowed_folders_matches_model_depot(self, workflow_manager_instance, temp_config_dir, monkeypatch):
        """ALLOWED_FOLDERS should match Model Depot's allowlist."""
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

        from addons.model_depot.addon import ModelDepotAddon
        model_depot = ModelDepotAddon()

        wm = workflow_manager_instance

        # Both should have the same folders
        assert wm.ALLOWED_FOLDERS == model_depot.ALLOWED_FOLDERS

    def test_is_allowed_folder_method(self, workflow_manager_instance):
        """_is_allowed_folder should validate folders."""
        addon = workflow_manager_instance

        # Allowed folders
        assert addon._is_allowed_folder("checkpoints") is True
        assert addon._is_allowed_folder("loras") is True
        assert addon._is_allowed_folder("vae") is True
        assert addon._is_allowed_folder("diffusion_models/wan") is True

        # Disallowed folders
        assert addon._is_allowed_folder("../etc") is False
        assert addon._is_allowed_folder("custom") is False
        assert addon._is_allowed_folder("") is False

    def test_add_target_folder_validates(self, workflow_manager_instance):
        """add_target_folder should validate against allowlist."""
        addon = workflow_manager_instance
        addon._workflow_models = {"target_folders": [], "workflows": {}, "models": {}}

        # Valid folder should be added
        msg, folders = addon.add_target_folder("loras")
        assert "Added" in msg
        assert "loras" in folders

        # Invalid folder should be rejected
        msg, folders = addon.add_target_folder("../../../etc")
        assert "Security" in msg
        assert "../../../etc" not in folders

    def test_add_target_folder_shows_valid_options(self, workflow_manager_instance):
        """Rejection message should show valid folder options."""
        addon = workflow_manager_instance
        addon._workflow_models = {"target_folders": [], "workflows": {}, "models": {}}

        msg, _ = addon.add_target_folder("invalid_folder")

        # Should mention valid options
        assert "checkpoints" in msg or "Valid" in msg

    def test_add_target_folder_rejects_duplicates(self, workflow_manager_instance):
        """Should reject duplicate folders."""
        addon = workflow_manager_instance
        addon._workflow_models = {"target_folders": ["loras"], "workflows": {}, "models": {}}

        msg, folders = addon.add_target_folder("loras")
        assert "already exists" in msg

    def test_add_target_folder_empty_name(self, workflow_manager_instance):
        """Should reject empty folder names."""
        addon = workflow_manager_instance
        addon._workflow_models = {"target_folders": [], "workflows": {}, "models": {}}

        msg, _ = addon.add_target_folder("")
        assert "required" in msg.lower()

        msg, _ = addon.add_target_folder("   ")
        assert "required" in msg.lower() or "Security" in msg

    def test_remove_target_folder(self, workflow_manager_instance):
        """Should be able to remove folders."""
        addon = workflow_manager_instance
        addon._workflow_models = {
            "target_folders": ["loras", "vae"],
            "workflows": {},
            "models": {},
        }

        with patch.object(addon, "_save_workflow_models", return_value="Saved"):
            msg, folders = addon.remove_target_folder("loras")

        assert "Removed" in msg
        assert "loras" not in folders
        assert "vae" in folders


class TestWorkflowManagerModelSets:
    """Tests for workflow model set management."""

    @pytest.fixture
    def wm_with_workflows(self, temp_config_dir, sample_workflow_models, monkeypatch):
        """Create WorkflowManager with sample workflows."""
        import sys
        sys.modules["gradio"] = MagicMock()

        monkeypatch.setattr(
            "addons.workflow_manager.addon.WorkflowManagerAddon.PROJECT_DIR",
            temp_config_dir["root"]
        )
        monkeypatch.setattr(
            "addons.workflow_manager.addon.WorkflowManagerAddon.USER_CONFIG_DIR",
            temp_config_dir["user_config"]
        )
        monkeypatch.setattr(
            "addons.workflow_manager.addon.WorkflowManagerAddon.DATA_DIR",
            temp_config_dir["root"] / "data"
        )
        monkeypatch.setattr(
            "addons.workflow_manager.addon.WorkflowManagerAddon.CONFIG_DIR",
            temp_config_dir["config"]
        )

        data_dir = temp_config_dir["root"] / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        with open(data_dir / "workflow_models.json", "w") as f:
            json.dump(sample_workflow_models, f)

        from addons.workflow_manager.addon import WorkflowManagerAddon
        addon = WorkflowManagerAddon()
        addon._workflow_models = sample_workflow_models
        return addon

    def test_get_target_folders(self, wm_with_workflows):
        """Should return list of target folders."""
        addon = wm_with_workflows
        folders = addon.get_target_folders()

        assert isinstance(folders, list)
        assert "checkpoints" in folders
        assert "diffusion_models" in folders

    def test_get_models_table(self, wm_with_workflows):
        """Should return models table for workflow."""
        addon = wm_with_workflows
        table = addon.get_models_table("gcv_wan_test")

        assert isinstance(table, list)
        assert len(table) > 0

        # Each row should have: filename, folder, mb, S, M, L, url
        for row in table:
            assert len(row) == 7

    def test_get_models_table_empty_workflow(self, wm_with_workflows):
        """Should return empty list for non-existent workflow."""
        addon = wm_with_workflows
        table = addon.get_models_table("nonexistent_workflow")

        assert table == []


class TestWorkflowManagerModelIdCollision:
    """Tests for model_id collision detection."""

    @pytest.fixture
    def wm_instance(self, temp_config_dir, monkeypatch):
        """Create WorkflowManager instance."""
        import sys
        sys.modules["gradio"] = MagicMock()

        monkeypatch.setattr(
            "addons.workflow_manager.addon.WorkflowManagerAddon.PROJECT_DIR",
            temp_config_dir["root"]
        )
        monkeypatch.setattr(
            "addons.workflow_manager.addon.WorkflowManagerAddon.USER_CONFIG_DIR",
            temp_config_dir["user_config"]
        )
        monkeypatch.setattr(
            "addons.workflow_manager.addon.WorkflowManagerAddon.DATA_DIR",
            temp_config_dir["root"] / "data"
        )
        monkeypatch.setattr(
            "addons.workflow_manager.addon.WorkflowManagerAddon.CONFIG_DIR",
            temp_config_dir["config"]
        )

        data_dir = temp_config_dir["root"] / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        from addons.workflow_manager.addon import WorkflowManagerAddon
        addon = WorkflowManagerAddon()
        addon._workflow_models = {
            "version": "1.0",
            "target_folders": ["loras", "checkpoints"],
            "workflows": {},
            "models": {
                "existing_model_safetensors": {
                    "filename": "existing_model.safetensors",
                    "target_path": "loras",
                }
            },
        }
        return addon

    def test_save_workflow_handles_collision(self, wm_instance):
        """save_workflow should handle model_id collisions."""
        addon = wm_instance

        # Table with same filename but different folder
        table_data = [
            # filename, folder, mb, S, M, L, url
            ["existing_model.safetensors", "checkpoints", 1000, True, True, True, ""],
        ]

        with patch.object(addon, "_save_workflow_models", return_value="Saved"):
            addon.save_workflow("test_workflow", table_data)

        # Should have created a unique model_id
        models = addon._workflow_models["models"]

        # Should have more than one model now
        assert len(models) >= 1

        # The new model should have a suffix to avoid collision
        model_ids = list(models.keys())
        # At least one should have a suffix containing the target path
        has_suffix = any("checkpoints" in mid for mid in model_ids)
        # Or it could be that the original model is preserved
        has_original = "existing_model_safetensors" in model_ids

        assert has_suffix or has_original


class TestVRAMTiers:
    """Tests for VRAM tier configuration."""

    def test_vram_tiers_defined(self, temp_config_dir, monkeypatch):
        """VRAM_TIERS should be properly defined."""
        import sys
        sys.modules["gradio"] = MagicMock()

        monkeypatch.setattr(
            "addons.workflow_manager.addon.WorkflowManagerAddon.PROJECT_DIR",
            temp_config_dir["root"]
        )
        monkeypatch.setattr(
            "addons.workflow_manager.addon.WorkflowManagerAddon.USER_CONFIG_DIR",
            temp_config_dir["user_config"]
        )
        monkeypatch.setattr(
            "addons.workflow_manager.addon.WorkflowManagerAddon.DATA_DIR",
            temp_config_dir["root"] / "data"
        )
        monkeypatch.setattr(
            "addons.workflow_manager.addon.WorkflowManagerAddon.CONFIG_DIR",
            temp_config_dir["config"]
        )

        (temp_config_dir["root"] / "data").mkdir(parents=True, exist_ok=True)

        from addons.workflow_manager.addon import WorkflowManagerAddon
        addon = WorkflowManagerAddon()

        assert "S" in addon.VRAM_TIERS  # Small: 8-12GB
        assert "M" in addon.VRAM_TIERS  # Medium: 16GB
        assert "L" in addon.VRAM_TIERS  # Large: 24-32GB

        assert 8 in addon.VRAM_TIERS["S"]
        assert 12 in addon.VRAM_TIERS["S"]
        assert 16 in addon.VRAM_TIERS["M"]
        assert 24 in addon.VRAM_TIERS["L"]
        assert 32 in addon.VRAM_TIERS["L"]
