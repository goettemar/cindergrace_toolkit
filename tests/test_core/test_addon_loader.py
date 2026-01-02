"""Tests for core/addon_loader.py - Addon loading system."""

import json

import pytest


class TestAddonLoader:
    """Tests for AddonLoader class."""

    def test_get_available_releases(self, temp_config_dir, sample_release_config, monkeypatch):
        """Should list available release configurations."""
        releases_dir = temp_config_dir["config"] / "releases"
        releases_dir.mkdir(parents=True)

        # Create some release files
        for name in ["full", "minimal", "runpod"]:
            with open(releases_dir / f"{name}.json", "w") as f:
                json.dump(sample_release_config, f)

        monkeypatch.setattr("core.addon_loader.AddonLoader.RELEASES_DIR", releases_dir)
        monkeypatch.setattr(
            "core.addon_loader.AddonLoader.ADDONS_DIR", temp_config_dir["root"] / "addons"
        )

        from core.addon_loader import AddonLoader

        loader = AddonLoader()

        releases = loader.get_available_releases()
        assert "full" in releases
        assert "minimal" in releases
        assert "runpod" in releases
        assert len(releases) == 3

    def test_get_available_releases_empty(self, temp_config_dir, monkeypatch):
        """Should return empty list when no releases exist."""
        releases_dir = temp_config_dir["config"] / "releases"
        # Don't create the directory

        monkeypatch.setattr("core.addon_loader.AddonLoader.RELEASES_DIR", releases_dir)
        monkeypatch.setattr(
            "core.addon_loader.AddonLoader.ADDONS_DIR", temp_config_dir["root"] / "addons"
        )

        from core.addon_loader import AddonLoader

        loader = AddonLoader()

        assert loader.get_available_releases() == []

    def test_load_release_config(self, temp_config_dir, sample_release_config, monkeypatch):
        """Should load release configuration from file."""
        releases_dir = temp_config_dir["config"] / "releases"
        releases_dir.mkdir(parents=True)

        with open(releases_dir / "test.json", "w") as f:
            json.dump(sample_release_config, f)

        monkeypatch.setattr("core.addon_loader.AddonLoader.RELEASES_DIR", releases_dir)
        monkeypatch.setattr(
            "core.addon_loader.AddonLoader.ADDONS_DIR", temp_config_dir["root"] / "addons"
        )

        from core.addon_loader import AddonLoader

        loader = AddonLoader()

        config = loader.load_release_config("test")
        assert config["name"] == "Test Release"
        assert config["version"] == "1.0.0"
        assert len(config["addons"]) == 3

    def test_load_release_config_not_found(self, temp_config_dir, monkeypatch):
        """Should raise FileNotFoundError for missing release."""
        releases_dir = temp_config_dir["config"] / "releases"
        releases_dir.mkdir(parents=True)

        monkeypatch.setattr("core.addon_loader.AddonLoader.RELEASES_DIR", releases_dir)
        monkeypatch.setattr(
            "core.addon_loader.AddonLoader.ADDONS_DIR", temp_config_dir["root"] / "addons"
        )

        from core.addon_loader import AddonLoader

        loader = AddonLoader()

        with pytest.raises(FileNotFoundError):
            loader.load_release_config("nonexistent")

    def test_get_available_addons(self, temp_config_dir, monkeypatch):
        """Should scan addons directory for available addons."""
        addons_dir = temp_config_dir["root"] / "addons"
        addons_dir.mkdir()

        # Create addon structures
        for addon_name in ["model_depot", "workflow_manager", "system_info"]:
            addon_dir = addons_dir / addon_name
            addon_dir.mkdir()
            (addon_dir / "addon.py").touch()
            (addon_dir / "__init__.py").touch()

        # Create a directory without addon.py (should be ignored)
        (addons_dir / "incomplete").mkdir()

        # Create a private directory (should be ignored)
        (addons_dir / "_private").mkdir()
        (addons_dir / "_private" / "addon.py").touch()

        monkeypatch.setattr("core.addon_loader.AddonLoader.ADDONS_DIR", addons_dir)
        monkeypatch.setattr(
            "core.addon_loader.AddonLoader.RELEASES_DIR", temp_config_dir["config"] / "releases"
        )

        from core.addon_loader import AddonLoader

        loader = AddonLoader()

        addons = loader.get_available_addons()
        assert "model_depot" in addons
        assert "workflow_manager" in addons
        assert "system_info" in addons
        assert "incomplete" not in addons
        assert "_private" not in addons

    def test_load_addon_caches_result(self, temp_config_dir, monkeypatch):
        """Loading same addon twice should return cached instance."""
        addons_dir = temp_config_dir["root"] / "addons"
        addons_dir.mkdir()

        # Create a simple addon
        test_addon_dir = addons_dir / "test_addon"
        test_addon_dir.mkdir()
        with open(test_addon_dir / "addon.py", "w") as f:
            f.write("""
from core.base_addon import BaseAddon
import gradio as gr

class TestAddonAddon(BaseAddon):
    def __init__(self):
        super().__init__()
        self.name = "Test"

    def get_tab_name(self):
        return "Test"

    def render(self):
        with gr.Blocks() as ui:
            gr.Markdown("Test")
        return ui
""")

        monkeypatch.setattr("core.addon_loader.AddonLoader.ADDONS_DIR", addons_dir)
        monkeypatch.setattr(
            "core.addon_loader.AddonLoader.RELEASES_DIR", temp_config_dir["config"] / "releases"
        )

        from core.addon_loader import AddonLoader

        loader = AddonLoader()

        # Load twice
        addon1 = loader.load_addon("test_addon")
        addon2 = loader.load_addon("test_addon")

        # Should be the same instance
        assert addon1 is addon2

    def test_load_addon_not_found(self, temp_config_dir, monkeypatch):
        """Should return None for non-existent addon."""
        addons_dir = temp_config_dir["root"] / "addons"
        addons_dir.mkdir()

        monkeypatch.setattr("core.addon_loader.AddonLoader.ADDONS_DIR", addons_dir)
        monkeypatch.setattr(
            "core.addon_loader.AddonLoader.RELEASES_DIR", temp_config_dir["config"] / "releases"
        )

        from core.addon_loader import AddonLoader

        loader = AddonLoader()

        result = loader.load_addon("nonexistent")
        assert result is None

    def test_unload_addon(self, temp_config_dir, monkeypatch):
        """Should be able to unload an addon."""
        addons_dir = temp_config_dir["root"] / "addons"
        addons_dir.mkdir()

        test_addon_dir = addons_dir / "unload_test"
        test_addon_dir.mkdir()
        with open(test_addon_dir / "addon.py", "w") as f:
            f.write("""
from core.base_addon import BaseAddon
import gradio as gr

class UnloadTestAddon(BaseAddon):
    def get_tab_name(self):
        return "Unload Test"

    def render(self):
        with gr.Blocks() as ui:
            gr.Markdown("Test")
        return ui
""")

        monkeypatch.setattr("core.addon_loader.AddonLoader.ADDONS_DIR", addons_dir)
        monkeypatch.setattr(
            "core.addon_loader.AddonLoader.RELEASES_DIR", temp_config_dir["config"] / "releases"
        )

        from core.addon_loader import AddonLoader

        loader = AddonLoader()

        loader.load_addon("unload_test")
        assert len(loader.get_loaded_addons()) == 1

        result = loader.unload_addon("unload_test")
        assert result is True
        assert len(loader.get_loaded_addons()) == 0

    def test_unload_nonexistent_addon(self, temp_config_dir, monkeypatch):
        """Unloading non-loaded addon should return False."""
        monkeypatch.setattr(
            "core.addon_loader.AddonLoader.ADDONS_DIR", temp_config_dir["root"] / "addons"
        )
        monkeypatch.setattr(
            "core.addon_loader.AddonLoader.RELEASES_DIR", temp_config_dir["config"] / "releases"
        )

        from core.addon_loader import AddonLoader

        loader = AddonLoader()

        result = loader.unload_addon("nonexistent")
        assert result is False

    def test_get_loaded_addons(self, temp_config_dir, monkeypatch):
        """Should return list of loaded addons."""
        monkeypatch.setattr(
            "core.addon_loader.AddonLoader.ADDONS_DIR", temp_config_dir["root"] / "addons"
        )
        monkeypatch.setattr(
            "core.addon_loader.AddonLoader.RELEASES_DIR", temp_config_dir["config"] / "releases"
        )

        from core.addon_loader import AddonLoader

        loader = AddonLoader()

        # Initially empty
        assert loader.get_loaded_addons() == []
