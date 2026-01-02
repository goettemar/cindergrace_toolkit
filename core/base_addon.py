"""Base class for all toolkit addons."""

from abc import ABC, abstractmethod

import gradio as gr


class BaseAddon(ABC):
    """Abstract base class for toolkit addons.

    All addons must inherit from this class and implement
    the required methods.
    """

    def __init__(self):
        self.id: str = self.__class__.__name__.lower().replace("addon", "")
        self.name: str = "Unnamed Addon"
        self.description: str = ""
        self.version: str = "1.0.0"
        self.icon: str = "🔧"

    @abstractmethod
    def get_tab_name(self) -> str:
        """Return the name displayed in the tab header."""
        pass

    @abstractmethod
    def render(self) -> gr.Blocks:
        """Render the addon UI and return the Gradio Blocks component."""
        pass

    def on_load(self) -> None:
        """Called when the addon is loaded. Override for initialization."""
        pass

    def on_unload(self) -> None:
        """Called when the addon is unloaded. Override for cleanup."""
        pass

    def get_info(self) -> dict:
        """Return addon metadata."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "icon": self.icon,
        }
