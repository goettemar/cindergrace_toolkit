"""Custom Nodes Manager Addon - Manage ComfyUI custom nodes from config."""

import json
import os
import subprocess
import sys
import threading
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
    id: str
    name: str
    url: str
    description: str
    enabled: bool
    required: bool
    status: NodeStatus = NodeStatus.MISSING
    folder_name: str = ""


class CustomNodesManagerAddon(BaseAddon):
    """Custom Nodes Manager - Install and update custom nodes from config."""

    PROJECT_DIR = Path(__file__).parent.parent.parent
    DATA_DIR = PROJECT_DIR / "data"
    CONFIG_DIR = PROJECT_DIR / "config"
    USER_CONFIG_DIR = PROJECT_DIR / ".config"
    SCRIPTS_DIR = PROJECT_DIR / "scripts"
    LOGS_DIR = PROJECT_DIR / "logs"

    def __init__(self):
        super().__init__()
        self.name = "Custom Nodes"
        self.version = "1.0.0"
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
        self._nodes_config = {"version": "1.0.0", "nodes": []}

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

    def _get_folder_name(self, url: str, folder_override: str = None) -> str:
        """Extract folder name from git URL or use override."""
        if folder_override:
            return folder_override
        name = url.rstrip("/").rstrip(".git").split("/")[-1]
        return name

    def _get_nodes(self) -> List[NodeInfo]:
        """Get all nodes with their status."""
        nodes = []

        for node_data in self._nodes_config.get("nodes", []):
            folder_override = node_data.get("folder", None)
            node = NodeInfo(
                id=node_data.get("id", ""),
                name=node_data.get("name", ""),
                url=node_data.get("url", ""),
                description=node_data.get("description", ""),
                enabled=node_data.get("enabled", False),
                required=node_data.get("required", False),
                folder_name=self._get_folder_name(node_data.get("url", ""), folder_override)
            )

            # Check installation status
            if self._custom_nodes_path and node.folder_name:
                node_path = self._custom_nodes_path / node.folder_name
                if node_path.exists():
                    if node.enabled:
                        node.status = NodeStatus.INSTALLED
                    else:
                        node.status = NodeStatus.DISABLED
                else:
                    node.status = NodeStatus.MISSING

            # Check if currently syncing
            if node.id in self._sync_status:
                if "updating" in self._sync_status[node.id].lower():
                    node.status = NodeStatus.UPDATING
                elif "error" in self._sync_status[node.id].lower():
                    node.status = NodeStatus.ERROR

            nodes.append(node)

        return nodes

    def _get_nodes_table(self) -> List[List[Any]]:
        """Get nodes as table data."""
        nodes = self._get_nodes()
        table = []

        for node in nodes:
            status_icon = {
                NodeStatus.INSTALLED: "✅",
                NodeStatus.MISSING: "❌",
                NodeStatus.DISABLED: "⏸️",
                NodeStatus.UPDATING: "🔄",
                NodeStatus.ERROR: "⚠️",
            }.get(node.status, "?")

            enabled_icon = "✅" if node.enabled else "❌"
            required_icon = "🔒" if node.required else ""

            table.append([
                status_icon,
                enabled_icon,
                f"{node.name} {required_icon}".strip(),
                node.description[:50] + "..." if len(node.description) > 50 else node.description,
                node.id
            ])

        return table

    def _toggle_node(self, node_id: str, enable: bool) -> str:
        """Enable or disable a node in config."""
        for node in self._nodes_config.get("nodes", []):
            if node.get("id") == node_id:
                if node.get("required", False) and not enable:
                    return f"Cannot disable required node: {node.get('name')}"
                node["enabled"] = enable
                self._save_nodes_config()
                return f"{'Enabled' if enable else 'Disabled'}: {node.get('name')}"

        return f"Node not found: {node_id}"

    def _run_sync(self, remove_disabled: bool = False) -> str:
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

    def _add_node(self, name: str, url: str, description: str) -> str:
        """Add a new node to config."""
        if not name or not url:
            return "Name and URL are required"

        # Generate ID from name
        node_id = name.lower().replace(" ", "-").replace("_", "-")

        # Check if already exists
        for node in self._nodes_config.get("nodes", []):
            if node.get("id") == node_id or node.get("url") == url:
                return f"Node already exists: {node.get('name')}"

        new_node = {
            "id": node_id,
            "name": name,
            "url": url,
            "description": description,
            "enabled": True
        }

        self._nodes_config.setdefault("nodes", []).append(new_node)
        self._save_nodes_config()
        return f"Added: {name}"

    def _remove_node(self, node_id: str) -> str:
        """Remove a node from config."""
        nodes = self._nodes_config.get("nodes", [])

        for i, node in enumerate(nodes):
            if node.get("id") == node_id:
                if node.get("required", False):
                    return f"Cannot remove required node: {node.get('name')}"
                removed = nodes.pop(i)
                self._save_nodes_config()
                return f"Removed: {removed.get('name')}"

        return f"Node not found: {node_id}"

    def _get_node_choices(self) -> List[Tuple[str, str]]:
        """Get node choices for dropdowns as (display_name, id) tuples."""
        choices = []
        for node_data in self._nodes_config.get("nodes", []):
            node_id = node_data.get("id", "")
            name = node_data.get("name", node_id)
            choices.append((f"{name} ({node_id})", node_id))
        return sorted(choices, key=lambda x: x[0])

    def _get_orphaned_nodes(self) -> List[Dict[str, str]]:
        """Find nodes on disk that are not in config."""
        orphaned = []

        if not self._custom_nodes_path or not self._custom_nodes_path.exists():
            return orphaned

        # Get all folder names from config
        config_folders = set()
        for node_data in self._nodes_config.get("nodes", []):
            folder = node_data.get("folder") or self._get_folder_name(node_data.get("url", ""))
            config_folders.add(folder)

        # Scan custom_nodes directory
        for item in self._custom_nodes_path.iterdir():
            if item.is_dir() and not item.name.startswith(".") and item.name != "__pycache__":
                if item.name not in config_folders:
                    # Try to get git remote URL
                    git_url = ""
                    try:
                        result = subprocess.run(
                            ["git", "remote", "get-url", "origin"],
                            cwd=item,
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        if result.returncode == 0:
                            git_url = result.stdout.strip()
                    except Exception:
                        pass

                    orphaned.append({
                        "folder": item.name,
                        "url": git_url,
                        "path": str(item)
                    })

        return orphaned

    def _restore_orphaned_node(self, folder: str) -> str:
        """Re-add an orphaned node to config."""
        orphaned = self._get_orphaned_nodes()

        for node in orphaned:
            if node["folder"] == folder:
                # Generate node entry
                name = folder.replace("-", " ").replace("_", " ").title()
                node_id = folder.lower().replace(" ", "-")

                new_node = {
                    "id": node_id,
                    "name": name,
                    "url": node["url"] or f"https://github.com/unknown/{folder}",
                    "description": "Restored from disk",
                    "enabled": True,
                    "folder": folder
                }

                self._nodes_config.setdefault("nodes", []).append(new_node)
                self._save_nodes_config()
                return f"✅ Restored: {name}"

        return f"❌ Not found: {folder}"

    def _delete_orphaned_node(self, folder: str) -> str:
        """Delete an orphaned node from disk."""
        if not self._custom_nodes_path:
            return "❌ ComfyUI path not found"

        node_path = self._custom_nodes_path / folder
        if not node_path.exists():
            return f"❌ Folder not found: {folder}"

        # Safety check - must be in custom_nodes
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
        choices = []
        for node in orphaned:
            label = f"{node['folder']}"
            if node['url']:
                label += f" ({node['url'].split('/')[-1].replace('.git', '')})"
            choices.append((label, node['folder']))
        return choices

    def _get_error_logs(self) -> str:
        """Read error logs from sync and startup."""
        logs = []

        # Read sync errors
        sync_log = self.LOGS_DIR / "sync_errors.log"
        if sync_log.exists():
            try:
                content = sync_log.read_text(encoding="utf-8").strip()
                if content:
                    logs.append("=== Sync Errors ===\n" + content)
            except Exception:
                pass

        # Read startup errors
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
            gr.Markdown("*Manage ComfyUI custom nodes from `data/custom_nodes.json`*")

            # === Status Info ===
            with gr.Row():
                with gr.Column(scale=2):
                    comfy_status = "✅ " + str(self._comfyui_path) if self._comfyui_path else "❌ Not found"
                    gr.Markdown(f"**ComfyUI:** {comfy_status}")
                with gr.Column(scale=1):
                    node_count = len(self._nodes_config.get("nodes", []))
                    gr.Markdown(f"**Nodes defined:** {node_count}")

            # === Nodes Table ===
            nodes_table = gr.Dataframe(
                headers=["Status", "Enabled", "Name", "Description", "ID"],
                datatype=["str", "str", "str", "str", "str"],
                value=self._get_nodes_table(),
                label="Custom Nodes",
                interactive=False,
            )

            # === Sync Actions ===
            with gr.Row():
                sync_btn = gr.Button("🔄 Sync Nodes", variant="primary", scale=2)
                refresh_btn = gr.Button("Refresh", scale=1)

            with gr.Row():
                remove_disabled_cb = gr.Checkbox(
                    label="Remove disabled nodes from disk",
                    value=False,
                    scale=2
                )

            sync_output = gr.Textbox(label="Sync Output", lines=10, interactive=False)

            # =============================================
            # Toggle Node (Enable/Disable)
            # =============================================
            gr.Markdown("---")
            gr.Markdown("### ⚡ Toggle Node")
            gr.Markdown("*Enable or disable a node in the config*")

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
            gr.Markdown("*Add a new custom node to the config. Node ID is auto-generated from the name.*")

            with gr.Row():
                new_name = gr.Textbox(label="Name", placeholder="My Custom Node", scale=1)
                new_url = gr.Textbox(label="Git URL", placeholder="https://github.com/user/repo.git", scale=2)

            new_desc = gr.Textbox(label="Description", placeholder="What does this node do?")

            with gr.Row():
                add_btn = gr.Button("➕ Add Node", variant="primary")
                add_output = gr.Textbox(label="Result", lines=1, interactive=False, scale=2)

            # =============================================
            # Remove Node from Config
            # =============================================
            gr.Markdown("---")
            gr.Markdown("### 🗑️ Remove Node from Config")
            gr.Markdown("*Removes from config only. Use 'Remove disabled from disk' during sync to delete files.*")

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
            # Orphaned Nodes (on disk but not in config)
            # =============================================
            gr.Markdown("---")
            gr.Markdown("### 👻 Verwaiste Nodes")
            gr.Markdown("*Nodes auf der Disk die nicht in der Config sind (z.B. nach 'Remove from Config')*")

            orphaned_choices = self._get_orphaned_choices()
            orphaned_count = len(orphaned_choices)

            orphaned_info = gr.Markdown(
                f"**Gefunden:** {orphaned_count} verwaiste Node(s)" if orphaned_count > 0 else "✅ Keine verwaisten Nodes"
            )

            with gr.Row(visible=orphaned_count > 0) as orphaned_row:
                orphaned_dropdown = gr.Dropdown(
                    label="Verwaister Node",
                    choices=orphaned_choices,
                    value=None,
                    scale=2
                )
                restore_btn = gr.Button("♻️ Wiederherstellen", variant="primary", scale=1)
                delete_disk_btn = gr.Button("🗑️ Von Disk löschen", variant="stop", scale=1)

            orphaned_output = gr.Textbox(label="Ergebnis", lines=1, interactive=False, visible=orphaned_count > 0)

            refresh_orphaned_btn = gr.Button("🔄 Verwaiste Nodes suchen")

            # =============================================
            # Error Logs
            # =============================================
            gr.Markdown("---")
            gr.Markdown("### 📋 Error Logs")
            gr.Markdown("*Errors from sync and startup operations*")

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

            def on_sync(remove_disabled):
                result = self._run_sync(remove_disabled)
                self._load_nodes_config()  # Reload config after sync
                return result, self._get_nodes_table(), self._get_error_logs()

            def on_refresh():
                self._load_nodes_config()
                choices = self._get_node_choices()
                return (
                    self._get_nodes_table(),
                    gr.update(choices=choices),
                    gr.update(choices=choices),
                    self._get_error_logs()
                )

            def on_refresh_logs():
                return self._get_error_logs()

            def on_clear_logs():
                result = self._clear_error_logs()
                return self._get_error_logs(), result

            def on_enable(node_id):
                if not node_id:
                    return "Please select a node", self._get_nodes_table()
                result = self._toggle_node(node_id, True)
                return result, self._get_nodes_table()

            def on_disable(node_id):
                if not node_id:
                    return "Please select a node", self._get_nodes_table()
                result = self._toggle_node(node_id, False)
                return result, self._get_nodes_table()

            def on_add(name, url, desc):
                result = self._add_node(name, url, desc)
                self._load_nodes_config()  # Reload to get new choices
                choices = self._get_node_choices()
                return (
                    result,
                    self._get_nodes_table(),
                    "",  # Clear name
                    "",  # Clear url
                    "",  # Clear desc
                    gr.update(choices=choices),  # Update toggle dropdown
                    gr.update(choices=choices)   # Update remove dropdown
                )

            def on_remove(node_id):
                if not node_id:
                    return "Please select a node", self._get_nodes_table(), gr.update(), gr.update()
                result = self._remove_node(node_id)
                self._load_nodes_config()  # Reload to update choices
                choices = self._get_node_choices()
                return (
                    result,
                    self._get_nodes_table(),
                    gr.update(choices=choices, value=None),  # Update toggle dropdown
                    gr.update(choices=choices, value=None)   # Update remove dropdown
                )

            def on_refresh_orphaned():
                orphaned = self._get_orphaned_choices()
                count = len(orphaned)
                info_text = f"**Gefunden:** {count} verwaiste Node(s)" if count > 0 else "✅ Keine verwaisten Nodes"
                return (
                    info_text,
                    gr.update(choices=orphaned, value=None, visible=count > 0),
                    gr.update(visible=count > 0)
                )

            def on_restore_orphaned(folder):
                if not folder:
                    return "Bitte Node auswählen", gr.update(), gr.update(), self._get_nodes_table(), gr.update(), gr.update()
                result = self._restore_orphaned_node(folder)
                self._load_nodes_config()
                # Refresh all lists
                orphaned = self._get_orphaned_choices()
                count = len(orphaned)
                info_text = f"**Gefunden:** {count} verwaiste Node(s)" if count > 0 else "✅ Keine verwaisten Nodes"
                choices = self._get_node_choices()
                return (
                    result,
                    info_text,
                    gr.update(choices=orphaned, value=None),
                    self._get_nodes_table(),
                    gr.update(choices=choices),
                    gr.update(choices=choices)
                )

            def on_delete_orphaned(folder):
                if not folder:
                    return "Bitte Node auswählen", gr.update(), gr.update()
                result = self._delete_orphaned_node(folder)
                # Refresh orphaned list
                orphaned = self._get_orphaned_choices()
                count = len(orphaned)
                info_text = f"**Gefunden:** {count} verwaiste Node(s)" if count > 0 else "✅ Keine verwaisten Nodes"
                return (
                    result,
                    info_text,
                    gr.update(choices=orphaned, value=None)
                )

            # === Wire Events ===
            sync_btn.click(
                on_sync,
                inputs=[remove_disabled_cb],
                outputs=[sync_output, nodes_table, error_logs]
            )

            refresh_btn.click(
                on_refresh,
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
                inputs=[toggle_dropdown],
                outputs=[toggle_output, nodes_table]
            )

            disable_btn.click(
                on_disable,
                inputs=[toggle_dropdown],
                outputs=[toggle_output, nodes_table]
            )

            add_btn.click(
                on_add,
                inputs=[new_name, new_url, new_desc],
                outputs=[add_output, nodes_table, new_name, new_url, new_desc, toggle_dropdown, remove_dropdown]
            )

            remove_btn.click(
                on_remove,
                inputs=[remove_dropdown],
                outputs=[remove_output, nodes_table, toggle_dropdown, remove_dropdown]
            )

            refresh_orphaned_btn.click(
                on_refresh_orphaned,
                outputs=[orphaned_info, orphaned_dropdown, orphaned_output]
            )

            restore_btn.click(
                on_restore_orphaned,
                inputs=[orphaned_dropdown],
                outputs=[orphaned_output, orphaned_info, orphaned_dropdown, nodes_table, toggle_dropdown, remove_dropdown]
            )

            delete_disk_btn.click(
                on_delete_orphaned,
                inputs=[orphaned_dropdown],
                outputs=[orphaned_output, orphaned_info, orphaned_dropdown]
            )

        return ui
