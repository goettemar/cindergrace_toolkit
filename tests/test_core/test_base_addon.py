"""Tests for core/base_addon.py - Base addon class."""

import pytest
from unittest.mock import MagicMock, patch


class TestBaseAddon:
    """Tests for BaseAddon abstract class."""

    def test_base_addon_is_abstract(self):
        """BaseAddon should not be instantiable directly."""
        from core.base_addon import BaseAddon

        with pytest.raises(TypeError):
            BaseAddon()

    def test_concrete_addon_must_implement_methods(self):
        """Concrete addon must implement abstract methods."""
        from core.base_addon import BaseAddon

        # Missing render() and get_tab_name()
        class IncompleteAddon(BaseAddon):
            pass

        with pytest.raises(TypeError):
            IncompleteAddon()

    def test_concrete_addon_works(self):
        """A properly implemented addon should work."""
        from core.base_addon import BaseAddon

        class TestAddon(BaseAddon):
            def get_tab_name(self) -> str:
                return "Test Tab"

            def render(self):
                return MagicMock()

        addon = TestAddon()
        assert addon.get_tab_name() == "Test Tab"

    def test_addon_id_auto_generated(self):
        """Addon ID should be auto-generated from class name."""
        from core.base_addon import BaseAddon

        class MyCustomAddon(BaseAddon):
            def get_tab_name(self) -> str:
                return "Custom"

            def render(self):
                return MagicMock()

        addon = MyCustomAddon()
        assert addon.id == "mycustom"  # "Addon" suffix removed, lowercased

    def test_addon_id_for_non_addon_suffix(self):
        """Addon ID should work even without 'Addon' suffix."""
        from core.base_addon import BaseAddon

        class MyWidget(BaseAddon):
            def get_tab_name(self) -> str:
                return "Widget"

            def render(self):
                return MagicMock()

        addon = MyWidget()
        assert addon.id == "mywidget"

    def test_default_attributes(self):
        """Addon should have sensible defaults."""
        from core.base_addon import BaseAddon

        class SimpleAddon(BaseAddon):
            def get_tab_name(self) -> str:
                return "Simple"

            def render(self):
                return MagicMock()

        addon = SimpleAddon()
        assert addon.name == "Unnamed Addon"
        assert addon.description == ""
        assert addon.version == "1.0.0"
        assert addon.icon == "🔧"

    def test_custom_attributes(self):
        """Addon attributes can be customized."""
        from core.base_addon import BaseAddon

        class CustomAddon(BaseAddon):
            def __init__(self):
                super().__init__()
                self.name = "My Custom Addon"
                self.description = "Does custom things"
                self.version = "2.0.0"
                self.icon = "✨"

            def get_tab_name(self) -> str:
                return f"{self.icon} {self.name}"

            def render(self):
                return MagicMock()

        addon = CustomAddon()
        assert addon.name == "My Custom Addon"
        assert addon.description == "Does custom things"
        assert addon.version == "2.0.0"
        assert addon.icon == "✨"

    def test_get_info_returns_metadata(self):
        """get_info() should return addon metadata."""
        from core.base_addon import BaseAddon

        class InfoAddon(BaseAddon):
            def __init__(self):
                super().__init__()
                self.name = "Info Addon"
                self.description = "Test description"
                self.version = "3.0.0"
                self.icon = "📋"

            def get_tab_name(self) -> str:
                return "Info"

            def render(self):
                return MagicMock()

        addon = InfoAddon()
        info = addon.get_info()

        assert info["id"] == "info"
        assert info["name"] == "Info Addon"
        assert info["description"] == "Test description"
        assert info["version"] == "3.0.0"
        assert info["icon"] == "📋"

    def test_on_load_called(self):
        """on_load() should be callable."""
        from core.base_addon import BaseAddon

        class LoadableAddon(BaseAddon):
            def __init__(self):
                super().__init__()
                self.loaded = False

            def get_tab_name(self) -> str:
                return "Loadable"

            def render(self):
                return MagicMock()

            def on_load(self):
                self.loaded = True

        addon = LoadableAddon()
        assert addon.loaded is False

        addon.on_load()
        assert addon.loaded is True

    def test_on_unload_called(self):
        """on_unload() should be callable for cleanup."""
        from core.base_addon import BaseAddon

        class CleanupAddon(BaseAddon):
            def __init__(self):
                super().__init__()
                self.resources = ["resource1", "resource2"]

            def get_tab_name(self) -> str:
                return "Cleanup"

            def render(self):
                return MagicMock()

            def on_unload(self):
                self.resources.clear()

        addon = CleanupAddon()
        assert len(addon.resources) == 2

        addon.on_unload()
        assert len(addon.resources) == 0
