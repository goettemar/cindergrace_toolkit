"""Configuration manager for toolkit settings."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


class ConfigManager:
    """Manage toolkit configuration.

    Handles:
    - Local settings
    - ComfyUI paths detection
    - Remote profile URLs
    """

    PROJECT_DIR = Path(__file__).parent.parent
    CONFIG_DIR = PROJECT_DIR / "config"
    USER_CONFIG_DIR = PROJECT_DIR / ".config"
    SETTINGS_FILE = CONFIG_DIR / "settings.json"

    DEFAULT_SETTINGS = {
        "comfyui_path": "",
        "models_path": "",
        "remote_profiles_url": "https://raw.githubusercontent.com/USERNAME/cindergrace_toolkit_profiles/main/",
        "auto_sync_profiles": True,
        "download_parallel": 2,
        "show_file_sizes": True,
        "confirm_delete": True,
        "theme": "default",
    }

    def __init__(self):
        self._settings: Dict[str, Any] = {}
        self._config: Dict[str, Any] = {}  # Main config.json
        self._load_settings()
        self._load_config()

    def _load_settings(self) -> None:
        """Load settings from file or create defaults."""
        if self.SETTINGS_FILE.exists():
            try:
                with open(self.SETTINGS_FILE, "r", encoding="utf-8") as f:
                    self._settings = json.load(f)
            except Exception:
                self._settings = self.DEFAULT_SETTINGS.copy()
        else:
            self._settings = self.DEFAULT_SETTINGS.copy()
            self._save_settings()

    def _save_settings(self) -> None:
        """Save settings to file."""
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(self._settings, f, indent=2, ensure_ascii=False)

    def _load_config(self) -> None:
        """Load main config.json (same as addons use)."""
        # Priority: .config/config.json > config/config.json
        user_file = self.USER_CONFIG_DIR / "config.json"
        default_file = self.CONFIG_DIR / "config.json"

        if user_file.exists():
            try:
                with open(user_file, "r", encoding="utf-8") as f:
                    self._config = json.load(f)
            except Exception:
                self._config = {}
        elif default_file.exists():
            try:
                with open(default_file, "r", encoding="utf-8") as f:
                    self._config = json.load(f)
            except Exception:
                self._config = {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a setting value and save."""
        self._settings[key] = value
        self._save_settings()

    def get_all(self) -> Dict[str, Any]:
        """Get all settings."""
        return self._settings.copy()

    def reset(self) -> None:
        """Reset to default settings."""
        self._settings = self.DEFAULT_SETTINGS.copy()
        self._save_settings()

    # === ComfyUI Path Detection ===

    def detect_comfyui_path(self) -> Optional[str]:
        """Auto-detect ComfyUI installation path."""
        common_paths = [
            # Local common paths
            Path.home() / "ComfyUI",
            Path("/workspace/ComfyUI"),  # RunPod
            Path("/content/ComfyUI"),    # Colab
            Path("C:/ComfyUI"),          # Windows
            Path("D:/ComfyUI"),
            # Relative
            Path("../ComfyUI"),
            Path("../../ComfyUI"),
        ]

        for path in common_paths:
            if path.exists() and (path / "main.py").exists():
                return str(path.absolute())

        return None

    def get_comfyui_path(self) -> Optional[str]:
        """Get ComfyUI path from config.json (same as addons)."""
        paths_config = self._config.get("paths", {})
        env = self.get_environment()

        # Try config.json paths first
        comfy_path = paths_config.get("comfyui", {}).get(env, "")
        if comfy_path:
            if comfy_path.startswith("~"):
                comfy_path = os.path.expanduser(comfy_path)
            if os.path.exists(comfy_path):
                return comfy_path

        # Fallback to auto-detection
        detected = self.detect_comfyui_path()
        return detected

    def get_models_path(self) -> Optional[str]:
        """Get ComfyUI models directory path."""
        comfy_path = self.get_comfyui_path()
        if comfy_path:
            models_path = Path(comfy_path) / "models"
            if models_path.exists():
                return str(models_path)
        return None

    def is_runpod(self) -> bool:
        """Check if running on RunPod."""
        # Check for RunPod environment variable or /workspace without /content (Colab)
        return bool(os.environ.get("RUNPOD_POD_ID")) or (
            os.path.exists("/workspace") and not os.path.exists("/content")
        )

    def is_colab(self) -> bool:
        """Check if running on Google Colab."""
        return os.path.exists("/content") and "COLAB_GPU" in os.environ

    def get_environment(self) -> str:
        """Get current environment type."""
        if self.is_runpod():
            return "runpod"
        if self.is_colab():
            return "colab"
        return "local"
