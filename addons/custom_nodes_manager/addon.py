"""Custom Nodes Manager Addon - Manage ComfyUI custom nodes using cm-cli."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

import gradio as gr

from core.base_addon import BaseAddon


class NodeStatus(Enum):
    """Status of a custom node."""
    INSTALLED = "installed"
    MISSING = "missing"
    DISABLED = "disabled"
    UPDATING = "updating"
    ERROR = "error"


@dataclass
class NodeInfo:
    """Custom node information."""
    name: str
    description: str
    enabled: bool
    status: NodeStatus = NodeStatus.MISSING


class CustomNodesManagerAddon(BaseAddon):
    """Custom Nodes Manager - Install and manage nodes via ComfyUI-Manager CLI."""

    PROJECT_DIR = Path(__file__).parent.parent.parent
    DATA_DIR = PROJECT_DIR / "data"
    CONFIG_DIR = PROJECT_DIR / "config"
    USER_CONFIG_DIR = PROJECT_DIR / ".config"
    SCRIPTS_DIR = PROJECT_DIR / "scripts"
    LOGS_DIR = PROJECT_DIR / "logs"

    def __init__(self):
        super().__init__()
        self.name = "Custom Nodes"
        self.version = "2.0.0"
        self.icon = "🔧"

        self._config: Dict[str, Any] = {}
        self._nodes_config: Dict[str, Any] = {}
        self._comfyui_path: Optional[Path] = None
        self._custom_nodes_path: Optional[Path] = None

        self._sync_status: Dict[str, str] = {}
        self._sync_running = False

    def get_tab_name(self) -> str:
        return f"{self.icon} {self.name}"

    def on_load(self) -> None:
        self._load_config()
        self._load_nodes_config()
        self._detect_paths()

    def _load_config(self) -> None:
        """Load main config."""
        for config_path in [self.USER_CONFIG_DIR / "config.json", self.CONFIG_DIR / "config.json"]:
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    self._config = json.load(f)
                break

    def _load_nodes_config(self) -> None:
        """Load custom_nodes.json."""
        self._nodes_config = {"version": "2.0.0", "nodes": []}

        config_file = self.DATA_DIR / "custom_nodes.json"
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                self._nodes_config = json.load(f)

    def _save_nodes_config(self) -> None:
        """Save custom_nodes.json."""
        config_file = self.DATA_DIR / "custom_nodes.json"
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(self._nodes_config, f, indent=2, ensure_ascii=False)

    def _detect_paths(self) -> None:
        """Detect ComfyUI path."""
        paths_config = self._config.get("paths", {})

        if os.path.exists("/workspace"):
            env = "runpod"
        elif os.path.exists("/content"):
            env = "colab"
        else:
            env = "local"

        comfy_path = paths_config.get("comfyui", {}).get(env, "")
        if comfy_path.startswith("~"):
            comfy_path = os.path.expanduser(comfy_path)

        if comfy_path and os.path.exists(comfy_path):
            self._comfyui_path = Path(comfy_path)
            self._custom_nodes_path = self._comfyui_path / "custom_nodes"

    def _get_nodes(self) -> List[NodeInfo]:
        """Get all nodes with their status."""
        nodes = []

        for node_data in self._nodes_config.get("nodes", []):
            name = node_data.get("name", "")
            if not name:
                continue

            node = NodeInfo(
                name=name,
                description=node_data.get("description", ""),
                enabled=node_data.get("enabled", False),
            )

            # Check installation status by looking for folder
            if self._custom_nodes_path:
                # cm-cli uses the node name as folder name
                possible_folders = [
                    name,
                    name.replace(" ", "-"),
                    name.replace(" ", "_"),
                ]
                installed = False
                for folder in possible_folders:
                    if (self._custom_nodes_path / folder).exists():
                        installed = True
                        break

                if installed:
                    node.status = NodeStatus.INSTALLED if node.enabled else NodeStatus.DISABLED
                else:
                    node.status = NodeStatus.MISSING

            nodes.append(node)

        return nodes

    def _get_nodes_table(
        self,
        show_disabled: bool = True,
        show_missing: bool = True
    ) -> List[List[Any]]:
        """Get nodes as table data with optional filtering."""
        nodes = self._get_nodes()
        table = []

        for node in nodes:
            # Apply filters
            if not show_disabled and not node.enabled:
                continue
            if not show_missing and node.status == NodeStatus.MISSING:
                continue

            status_icon = {
                NodeStatus.INSTALLED: "✅",
                NodeStatus.MISSING: "❌",
                NodeStatus.DISABLED: "⏸️",
                NodeStatus.UPDATING: "🔄",
                NodeStatus.ERROR: "⚠️",
            }.get(node.status, "?")

            enabled_icon = "✅" if node.enabled else "❌"

            table.append([
                status_icon,
                enabled_icon,
                node.name,
                node.description[:50] + "..." if len(node.description) > 50 else node.description,
            ])

        return table

    def _toggle_node(self, node_name: str, enable: bool) -> str:
        """Enable or disable a node in config."""
        for node in self._nodes_config.get("nodes", []):
            if node.get("name") == node_name:
                node["enabled"] = enable
                self._save_nodes_config()
                return f"{'Enabled' if enable else 'Disabled'}: {node_name}"

        return f"Node not found: {node_name}"

    def _run_sync(self, remove_disabled: bool = False, update_all: bool = False) -> str:
        """Run the sync_nodes.py script."""
        if self._sync_running:
            return "Sync already running..."

        self._sync_running = True
        self._sync_status = {}

        script_path = self.SCRIPTS_DIR / "sync_nodes.py"
        if not script_path.exists():
            self._sync_running = False
            return f"Script not found: {script_path}"

        cmd = [sys.executable, str(script_path)]
        if self._comfyui_path:
            cmd.extend(["--comfyui-path", str(self._comfyui_path)])
        if remove_disabled:
            cmd.append("--remove-disabled")
        if update_all:
            cmd.append("--update-all")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600
            )
            self._sync_running = False
            return result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            self._sync_running = False
            return "Sync timed out after 10 minutes"
        except Exception as e:
            self._sync_running = False
            return f"Error: {e}"

    def _add_node(self, name: str, description: str) -> str:
        """Add a new node to config."""
        if not name:
            return "Node name is required"

        # Normalize name
        name = name.strip()

        # Check if already exists
        for node in self._nodes_config.get("nodes", []):
            if node.get("name", "").lower() == name.lower():
                return f"Node already exists: {node.get('name')}"

        new_node = {
            "name": name,
            "enabled": True,
            "description": description or ""
        }

        self._nodes_config.setdefault("nodes", []).append(new_node)
        self._save_nodes_config()
        return f"✅ Added: {name}\n\nRun 'Sync Nodes' to install."

    def _remove_node(self, node_name: str) -> str:
        """Remove a node from config."""
        nodes = self._nodes_config.get("nodes", [])

        for i, node in enumerate(nodes):
            if node.get("name") == node_name:
                removed = nodes.pop(i)
                self._save_nodes_config()
                return f"Removed from config: {removed.get('name')}\n\nUse 'Remove disabled' during sync to uninstall."

        return f"Node not found: {node_name}"

    def _get_node_choices(self) -> List[Tuple[str, str]]:
        """Get node choices for dropdowns as (display_name, name) tuples."""
        choices = []
        for node_data in self._nodes_config.get("nodes", []):
            name = node_data.get("name", "")
            if name:
                enabled = "✅" if node_data.get("enabled", False) else "❌"
                choices.append((f"{enabled} {name}", name))
        return sorted(choices, key=lambda x: x[0])

    def _get_orphaned_nodes(self) -> List[Dict[str, str]]:
        """Find nodes on disk that are not in config."""
        orphaned = []

        if not self._custom_nodes_path or not self._custom_nodes_path.exists():
            return orphaned

        # Get all node names from config
        config_names = set()
        for node_data in self._nodes_config.get("nodes", []):
            name = node_data.get("name", "")
            if name:
                config_names.add(name.lower())
                config_names.add(name.lower().replace(" ", "-"))
                config_names.add(name.lower().replace(" ", "_"))

        # Also add manager
        config_names.add("comfyui-manager")

        # Scan custom_nodes directory
        for item in self._custom_nodes_path.iterdir():
            if item.is_dir() and not item.name.startswith(".") and item.name != "__pycache__":
                if item.name.lower() not in config_names:
                    orphaned.append({
                        "folder": item.name,
                        "path": str(item)
                    })

        return orphaned

    def _restore_orphaned_node(self, folder: str) -> str:
        """Re-add an orphaned node to config."""
        # Generate a nice name from folder
        name = folder

        new_node = {
            "name": name,
            "description": "Restored from disk",
            "enabled": True,
        }

        self._nodes_config.setdefault("nodes", []).append(new_node)
        self._save_nodes_config()
        return f"✅ Restored: {name}"

    def _delete_orphaned_node(self, folder: str) -> str:
        """Delete an orphaned node from disk."""
        if not self._custom_nodes_path:
            return "❌ ComfyUI path not found"

        node_path = self._custom_nodes_path / folder
        if not node_path.exists():
            return f"❌ Folder not found: {folder}"

        # Safety check
        if self._custom_nodes_path not in node_path.parents and node_path.parent != self._custom_nodes_path:
            return "❌ Invalid path"

        try:
            import shutil
            shutil.rmtree(node_path)
            return f"✅ Deleted: {folder}"
        except Exception as e:
            return f"❌ Error: {e}"

    def _get_orphaned_choices(self) -> List[Tuple[str, str]]:
        """Get orphaned node choices for dropdown."""
        orphaned = self._get_orphaned_nodes()
        return [(node['folder'], node['folder']) for node in orphaned]

    def _get_error_logs(self) -> str:
        """Read error logs from sync and startup."""
        logs = []

        sync_log = self.LOGS_DIR / "sync_errors.log"
        if sync_log.exists():
            try:
                content = sync_log.read_text(encoding="utf-8").strip()
                if content:
                    logs.append("=== Sync Errors ===\n" + content)
            except Exception:
                pass

        startup_log = self.LOGS_DIR / "startup_errors.log"
        if startup_log.exists():
            try:
                content = startup_log.read_text(encoding="utf-8").strip()
                if content:
                    logs.append("=== Startup Errors ===\n" + content)
            except Exception:
                pass

        if not logs:
            return "No errors logged."

        return "\n\n".join(logs)

    def _clear_error_logs(self) -> str:
        """Clear all error logs."""
        cleared = []
        for log_name in ["sync_errors.log", "startup_errors.log"]:
            log_path = self.LOGS_DIR / log_name
            if log_path.exists():
                try:
                    log_path.unlink()
                    cleared.append(log_name)
                except Exception:
                    pass

        if cleared:
            return f"Cleared: {', '.join(cleared)}"
        return "No logs to clear."

    def render(self) -> gr.Blocks:
        """Render the Custom Nodes Manager UI."""

        with gr.Blocks() as ui:
            gr.Markdown("## 🔧 Custom Nodes Manager")
            gr.Markdown("*Manage ComfyUI custom nodes via ComfyUI-Manager CLI*")

            # === Status Info ===
            with gr.Row():
                with gr.Column(scale=2):
                    comfy_status = "✅ " + str(self._comfyui_path) if self._comfyui_path else "❌ Not found"
                    gr.Markdown(f"**ComfyUI:** {comfy_status}")
                with gr.Column(scale=1):
                    node_count = len(self._nodes_config.get("nodes", []))
                    gr.Markdown(f"**Nodes in config:** {node_count}")

            # === Nodes Table ===
            with gr.Row():
                filter_show_disabled = gr.Checkbox(label="Deaktivierte anzeigen", value=True, scale=1)
                filter_show_missing = gr.Checkbox(label="Fehlende anzeigen", value=True, scale=1)

            nodes_table = gr.Dataframe(
                headers=["Status", "Enabled", "Name", "Description"],
                datatype=["str", "str", "str", "str"],
                value=self._get_nodes_table(),
                label="Custom Nodes",
                interactive=False,
            )

            # === Sync Actions ===
            gr.Markdown("### ⚡ Sync Actions")
            with gr.Row():
                sync_btn = gr.Button("🔄 Sync Nodes", variant="primary", scale=2)
                update_all_btn = gr.Button("⬆️ Update All", scale=1)
                refresh_btn = gr.Button("🔃 Refresh", scale=1)

            with gr.Row():
                remove_disabled_cb = gr.Checkbox(
                    label="Remove disabled nodes from disk",
                    value=False,
                    scale=2
                )

            sync_output = gr.Textbox(label="Output", lines=10, interactive=False)

            # =============================================
            # Toggle Node (Enable/Disable)
            # =============================================
            gr.Markdown("---")
            gr.Markdown("### ⚡ Toggle Node")

            with gr.Row():
                toggle_dropdown = gr.Dropdown(
                    label="Select Node",
                    choices=self._get_node_choices(),
                    value=None,
                    scale=2
                )
                enable_btn = gr.Button("✅ Enable", scale=1)
                disable_btn = gr.Button("❌ Disable", scale=1)

            toggle_output = gr.Textbox(label="Result", lines=1, interactive=False)

            # =============================================
            # Add New Node
            # =============================================
            gr.Markdown("---")
            gr.Markdown("### ➕ Add New Node")
            gr.Markdown("*Enter the exact node name from ComfyUI-Manager (e.g. `ComfyUI-Impact-Pack`)*")

            with gr.Row():
                new_name = gr.Textbox(
                    label="Node Name",
                    placeholder="ComfyUI-Impact-Pack",
                    scale=2
                )
                new_desc = gr.Textbox(
                    label="Description (optional)",
                    placeholder="What does this node do?",
                    scale=2
                )

            with gr.Row():
                add_btn = gr.Button("➕ Add Node", variant="primary")
                add_output = gr.Textbox(label="Result", lines=2, interactive=False, scale=2)

            # =============================================
            # Remove Node from Config
            # =============================================
            gr.Markdown("---")
            gr.Markdown("### 🗑️ Remove Node from Config")

            with gr.Row():
                remove_dropdown = gr.Dropdown(
                    label="Select Node to Remove",
                    choices=self._get_node_choices(),
                    value=None,
                    scale=2
                )
                remove_btn = gr.Button("🗑️ Remove", variant="stop", scale=1)
                remove_output = gr.Textbox(label="Result", lines=1, interactive=False, scale=2)

            # =============================================
            # Orphaned Nodes
            # =============================================
            gr.Markdown("---")
            gr.Markdown("### 👻 Verwaiste Nodes")
            gr.Markdown("*Nodes auf der Disk die nicht in der Config sind*")

            orphaned_choices = self._get_orphaned_choices()
            orphaned_count = len(orphaned_choices)

            orphaned_info = gr.Markdown(
                f"**Gefunden:** {orphaned_count} verwaiste Node(s)" if orphaned_count > 0 else "✅ Keine verwaisten Nodes"
            )

            with gr.Row():
                orphaned_dropdown = gr.Dropdown(
                    label="Verwaister Node",
                    choices=orphaned_choices,
                    value=None,
                    scale=2,
                    visible=orphaned_count > 0
                )
                restore_btn = gr.Button("♻️ Wiederherstellen", scale=1, visible=orphaned_count > 0)
                delete_disk_btn = gr.Button("🗑️ Von Disk löschen", variant="stop", scale=1, visible=orphaned_count > 0)

            orphaned_output = gr.Textbox(label="Ergebnis", lines=1, interactive=False, visible=orphaned_count > 0)
            refresh_orphaned_btn = gr.Button("🔄 Verwaiste Nodes suchen")

            # =============================================
            # Error Logs
            # =============================================
            gr.Markdown("---")
            gr.Markdown("### 📋 Error Logs")

            error_logs = gr.Textbox(
                label="Errors",
                value=self._get_error_logs(),
                lines=6,
                interactive=False
            )

            with gr.Row():
                refresh_logs_btn = gr.Button("🔄 Refresh Logs", scale=1)
                clear_logs_btn = gr.Button("🗑️ Clear Logs", scale=1)
                clear_logs_output = gr.Textbox(label="", lines=1, interactive=False, scale=2)

            # === Event Handlers ===

            def on_filter_change(show_disabled, show_missing):
                return self._get_nodes_table(show_disabled, show_missing)

            def on_sync(remove_disabled, show_disabled, show_missing):
                result = self._run_sync(remove_disabled)
                self._load_nodes_config()
                return result, self._get_nodes_table(show_disabled, show_missing), self._get_error_logs()

            def on_update_all(show_disabled, show_missing):
                result = self._run_sync(update_all=True)
                return result, self._get_nodes_table(show_disabled, show_missing), self._get_error_logs()

            def on_refresh(show_disabled, show_missing):
                self._load_nodes_config()
                choices = self._get_node_choices()
                return (
                    self._get_nodes_table(show_disabled, show_missing),
                    gr.update(choices=choices),
                    gr.update(choices=choices),
                    self._get_error_logs()
                )

            def on_refresh_logs():
                return self._get_error_logs()

            def on_clear_logs():
                result = self._clear_error_logs()
                return self._get_error_logs(), result

            def on_enable(node_name, show_disabled, show_missing):
                if not node_name:
                    return "Please select a node", self._get_nodes_table(show_disabled, show_missing), gr.update()
                result = self._toggle_node(node_name, True)
                choices = self._get_node_choices()
                return result, self._get_nodes_table(show_disabled, show_missing), gr.update(choices=choices)

            def on_disable(node_name, show_disabled, show_missing):
                if not node_name:
                    return "Please select a node", self._get_nodes_table(show_disabled, show_missing), gr.update()
                result = self._toggle_node(node_name, False)
                choices = self._get_node_choices()
                return result, self._get_nodes_table(show_disabled, show_missing), gr.update(choices=choices)

            def on_add(name, desc, show_disabled, show_missing):
                result = self._add_node(name, desc)
                self._load_nodes_config()
                choices = self._get_node_choices()
                return (
                    result,
                    self._get_nodes_table(show_disabled, show_missing),
                    "",  # Clear name
                    "",  # Clear desc
                    gr.update(choices=choices),
                    gr.update(choices=choices)
                )

            def on_remove(node_name, show_disabled, show_missing):
                if not node_name:
                    return "Please select a node", self._get_nodes_table(show_disabled, show_missing), gr.update(), gr.update()
                result = self._remove_node(node_name)
                self._load_nodes_config()
                choices = self._get_node_choices()
                return (
                    result,
                    self._get_nodes_table(show_disabled, show_missing),
                    gr.update(choices=choices, value=None),
                    gr.update(choices=choices, value=None)
                )

            def on_refresh_orphaned():
                orphaned = self._get_orphaned_choices()
                count = len(orphaned)
                info_text = f"**Gefunden:** {count} verwaiste Node(s)" if count > 0 else "✅ Keine verwaisten Nodes"
                return (
                    info_text,
                    gr.update(choices=orphaned, value=None, visible=count > 0),
                    gr.update(visible=count > 0),
                    gr.update(visible=count > 0),
                    gr.update(visible=count > 0)
                )

            def on_restore_orphaned(folder, show_disabled, show_missing):
                if not folder:
                    return "Bitte Node auswählen", gr.update(), gr.update(), self._get_nodes_table(show_disabled, show_missing), gr.update(), gr.update()
                result = self._restore_orphaned_node(folder)
                self._load_nodes_config()
                orphaned = self._get_orphaned_choices()
                count = len(orphaned)
                info_text = f"**Gefunden:** {count} verwaiste Node(s)" if count > 0 else "✅ Keine verwaisten Nodes"
                choices = self._get_node_choices()
                return (
                    result,
                    info_text,
                    gr.update(choices=orphaned, value=None),
                    self._get_nodes_table(show_disabled, show_missing),
                    gr.update(choices=choices),
                    gr.update(choices=choices)
                )

            def on_delete_orphaned(folder):
                if not folder:
                    return "Bitte Node auswählen", gr.update(), gr.update()
                result = self._delete_orphaned_node(folder)
                orphaned = self._get_orphaned_choices()
                count = len(orphaned)
                info_text = f"**Gefunden:** {count} verwaiste Node(s)" if count > 0 else "✅ Keine verwaisten Nodes"
                return (
                    result,
                    info_text,
                    gr.update(choices=orphaned, value=None)
                )

            # === Wire Events ===

            # Filter changes
            filter_show_disabled.change(
                on_filter_change,
                inputs=[filter_show_disabled, filter_show_missing],
                outputs=[nodes_table]
            )
            filter_show_missing.change(
                on_filter_change,
                inputs=[filter_show_disabled, filter_show_missing],
                outputs=[nodes_table]
            )

            sync_btn.click(
                on_sync,
                inputs=[remove_disabled_cb, filter_show_disabled, filter_show_missing],
                outputs=[sync_output, nodes_table, error_logs]
            )

            update_all_btn.click(
                on_update_all,
                inputs=[filter_show_disabled, filter_show_missing],
                outputs=[sync_output, nodes_table, error_logs]
            )

            refresh_btn.click(
                on_refresh,
                inputs=[filter_show_disabled, filter_show_missing],
                outputs=[nodes_table, toggle_dropdown, remove_dropdown, error_logs]
            )

            refresh_logs_btn.click(
                on_refresh_logs,
                outputs=[error_logs]
            )

            clear_logs_btn.click(
                on_clear_logs,
                outputs=[error_logs, clear_logs_output]
            )

            enable_btn.click(
                on_enable,
                inputs=[toggle_dropdown, filter_show_disabled, filter_show_missing],
                outputs=[toggle_output, nodes_table, toggle_dropdown]
            )

            disable_btn.click(
                on_disable,
                inputs=[toggle_dropdown, filter_show_disabled, filter_show_missing],
                outputs=[toggle_output, nodes_table, toggle_dropdown]
            )

            add_btn.click(
                on_add,
                inputs=[new_name, new_desc, filter_show_disabled, filter_show_missing],
                outputs=[add_output, nodes_table, new_name, new_desc, toggle_dropdown, remove_dropdown]
            )

            remove_btn.click(
                on_remove,
                inputs=[remove_dropdown, filter_show_disabled, filter_show_missing],
                outputs=[remove_output, nodes_table, toggle_dropdown, remove_dropdown]
            )

            refresh_orphaned_btn.click(
                on_refresh_orphaned,
                outputs=[orphaned_info, orphaned_dropdown, restore_btn, delete_disk_btn, orphaned_output]
            )

            restore_btn.click(
                on_restore_orphaned,
                inputs=[orphaned_dropdown, filter_show_disabled, filter_show_missing],
                outputs=[orphaned_output, orphaned_info, orphaned_dropdown, nodes_table, toggle_dropdown, remove_dropdown]
            )

            delete_disk_btn.click(
                on_delete_orphaned,
                inputs=[orphaned_dropdown],
                outputs=[orphaned_output, orphaned_info, orphaned_dropdown]
            )

        return ui
