"""Addon loader with release profile support."""

import importlib
import json
from pathlib import Path
from typing import Any

from core.base_addon import BaseAddon


class AddonLoader:
    """Load addons based on release configuration.

    Supports:
    - Local release configs from config/releases/
    - Remote release configs from URL (GitHub, etc.)
    - Dynamic addon loading at runtime
    """

    ADDONS_DIR = Path(__file__).parent.parent / "addons"
    RELEASES_DIR = Path(__file__).parent.parent / "config" / "releases"

    def __init__(self):
        self._loaded_addons: dict[str, BaseAddon] = {}
        self._release_config: dict[str, Any] | None = None

    def get_available_releases(self) -> list[str]:
        """Get list of available release configurations."""
        releases = []
        if self.RELEASES_DIR.exists():
            for f in self.RELEASES_DIR.glob("*.json"):
                releases.append(f.stem)
        return sorted(releases)

    def get_available_addons(self) -> list[str]:
        """Scan addons directory for available addons."""
        addons = []
        if self.ADDONS_DIR.exists():
            for d in self.ADDONS_DIR.iterdir():
                if d.is_dir() and not d.name.startswith("_"):
                    addon_file = d / "addon.py"
                    if addon_file.exists():
                        addons.append(d.name)
        return sorted(addons)

    def load_release_config(self, release_name: str) -> dict[str, Any]:
        """Load release configuration from file or URL."""
        # Check if it's a URL (remote config)
        if release_name.startswith("http"):
            return self._load_remote_config(release_name)

        # Local config file
        config_path = self.RELEASES_DIR / f"{release_name}.json"
        if not config_path.exists():
            raise FileNotFoundError(f"Release config not found: {config_path}")

        with open(config_path, encoding="utf-8") as f:
            self._release_config = json.load(f)

        return self._release_config

    def _load_remote_config(self, url: str) -> dict[str, Any]:
        """Load release configuration from remote URL."""
        import urllib.request

        from core.ssl_utils import get_ssl_context

        # SSL context (secure by default, configurable via config.json)
        ctx = get_ssl_context()

        try:
            with urllib.request.urlopen(url, context=ctx, timeout=10) as response:
                content = response.read().decode("utf-8")
                self._release_config = json.loads(content)
                return self._release_config
        except Exception as e:
            raise RuntimeError(f"Failed to load remote config from {url}: {e}")

    def load_addon(self, addon_id: str) -> BaseAddon | None:
        """Load a single addon by ID."""
        if addon_id in self._loaded_addons:
            return self._loaded_addons[addon_id]

        addon_path = self.ADDONS_DIR / addon_id / "addon.py"
        if not addon_path.exists():
            print(f"Warning: Addon not found: {addon_id}")
            return None

        try:
            # Dynamic import
            spec = importlib.util.spec_from_file_location(f"addons.{addon_id}.addon", addon_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find the addon class (must end with "Addon")
            addon_class = None
            for name in dir(module):
                obj = getattr(module, name)
                if isinstance(obj, type) and issubclass(obj, BaseAddon) and obj is not BaseAddon:
                    addon_class = obj
                    break

            if addon_class is None:
                print(f"Warning: No addon class found in {addon_id}")
                return None

            # Instantiate and register
            addon = addon_class()
            addon.on_load()
            self._loaded_addons[addon_id] = addon
            print(f"Loaded addon: {addon.name} ({addon_id})")
            return addon

        except Exception as e:
            print(f"Error loading addon {addon_id}: {e}")
            return None

    def load_release(self, release_name: str) -> list[BaseAddon]:
        """Load all addons for a release configuration."""
        config = self.load_release_config(release_name)
        addons = []

        for addon_cfg in config.get("addons", []):
            addon_id = addon_cfg.get("id")
            enabled = addon_cfg.get("enabled", True)

            if enabled and addon_id:
                addon = self.load_addon(addon_id)
                if addon:
                    addons.append(addon)

        return addons

    def unload_addon(self, addon_id: str) -> bool:
        """Unload an addon."""
        if addon_id not in self._loaded_addons:
            return False

        addon = self._loaded_addons[addon_id]
        addon.on_unload()
        del self._loaded_addons[addon_id]
        return True

    def get_loaded_addons(self) -> list[BaseAddon]:
        """Get list of currently loaded addons."""
        return list(self._loaded_addons.values())
