"""Model Depot Addon - Workflow-based model management aligned with Workflow Manager."""

import json
import os
import shutil
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum

import gradio as gr

from core.base_addon import BaseAddon


class ModelStatus(Enum):
    """Status of a model file."""
    MISSING = "missing"
    PRESENT = "present"
    BACKUP_ONLY = "backup"
    DOWNLOADING = "downloading"
    ERROR = "error"


@dataclass
class ModelInfo:
    """Model information from workflow_models.json."""
    id: str
    filename: str
    url: str
    size_mb: int
    target_path: str
    status: ModelStatus = ModelStatus.MISSING
    comfy_size: int = 0  # Actual size in ComfyUI
    backup_size: int = 0  # Actual size in backup


def _sanitize_path(base_path: Path, target_path: str, filename: str) -> Optional[Path]:
    """Sanitize and validate a file path to prevent directory traversal.

    Args:
        base_path: The allowed base directory (e.g., models/ or backup/)
        target_path: Relative subdirectory (e.g., "diffusion_models/wan")
        filename: The filename

    Returns:
        Safe absolute path, or None if path is invalid/unsafe
    """
    # Block obvious traversal attempts
    if ".." in target_path or ".." in filename:
        return None
    if target_path.startswith("/") or filename.startswith("/"):
        return None

    # Normalize and resolve
    try:
        full_path = (base_path / target_path / filename).resolve()

        # Verify the resolved path is still under base_path
        base_resolved = base_path.resolve()
        if not str(full_path).startswith(str(base_resolved)):
            return None

        return full_path
    except (ValueError, OSError):
        return None


class ModelDepotAddon(BaseAddon):
    """Model Depot - aligned with Workflow Manager architecture.

    Uses same workflow_models.json structure with VRAM tiers (S/M/L).
    """

    PROJECT_DIR = Path(__file__).parent.parent.parent
    USER_CONFIG_DIR = PROJECT_DIR / ".config"
    DATA_DIR = PROJECT_DIR / "data"
    CONFIG_DIR = PROJECT_DIR / "config"

    # VRAM tiers matching Workflow Manager
    VRAM_TIERS = {"S": [8, 12], "M": [16], "L": [24, 32]}

    # Allowed target folders (whitelist)
    ALLOWED_FOLDERS = {
        "checkpoints", "clip_vision", "controlnet", "diffusion_models",
        "diffusion_models/wan", "loras", "loras/wan", "text_encoders",
        "upscale_models", "vae", "LLM"
    }

    def __init__(self):
        super().__init__()
        self.name = "Model Depot"
        self.version = "3.3.0"  # Security update
        self.icon = "📦"

        self._config: Dict[str, Any] = {}
        self._workflow_models: Dict[str, Any] = {}
        self._comfyui_path: Optional[Path] = None
        self._models_path: Optional[Path] = None
        self._workflows_path: Optional[Path] = None
        self._backup_path: Optional[Path] = None

        self._download_progress: Dict[str, float] = {}
        self._download_status: Dict[str, str] = {}

    def get_tab_name(self) -> str:
        return f"{self.icon} {self.name}"

    def on_load(self) -> None:
        self._load_config()
        self._load_workflow_models()
        self._detect_paths()

    def _load_config(self) -> None:
        user_file = self.USER_CONFIG_DIR / "config.json"
        default_file = self.CONFIG_DIR / "config.json"

        self._config_source = None
        if user_file.exists():
            with open(user_file, "r", encoding="utf-8") as f:
                self._config = json.load(f)
            self._config_source = ".config/config.json"
        elif default_file.exists():
            with open(default_file, "r", encoding="utf-8") as f:
                self._config = json.load(f)
            self._config_source = "config/config.json"

    def _load_workflow_models(self) -> None:
        """Load workflow_models.json from data/ (Git source)."""
        self._workflow_models = {
            "version": "1.1.0",
            "target_folders": [],
            "workflows": {},
            "models": {},
        }

        git_file = self.DATA_DIR / "workflow_models.json"
        if git_file.exists():
            with open(git_file, "r", encoding="utf-8") as f:
                self._workflow_models = json.load(f)
            self._models_source = "data/workflow_models.json"
        else:
            self._models_source = "not found"

    def _detect_paths(self) -> None:
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
            self._models_path = self._comfyui_path / "models"

            wf_template = paths_config.get("workflows", {}).get(env, "{comfyui}/user/default/workflows")
            wf_path = wf_template.replace("{comfyui}", comfy_path)
            if os.path.exists(wf_path):
                self._workflows_path = Path(wf_path)

        backup_path = paths_config.get("backup", {}).get(env, "")
        if backup_path and os.path.exists(backup_path):
            self._backup_path = Path(backup_path)

    def _is_allowed_folder(self, target_path: str) -> bool:
        """Check if target_path is in allowed folders whitelist."""
        if not target_path:
            return False

        # Direct match
        if target_path in self.ALLOWED_FOLDERS:
            return True

        # Check if it's a subfolder of an allowed folder
        for folder in self.ALLOWED_FOLDERS:
            if target_path.startswith(folder + "/"):
                return True

        return False

    def _get_disk_info(self) -> str:
        """Get disk space info for model paths."""

        def format_size(bytes_val: int) -> str:
            gb = bytes_val / (1024**3)
            if gb >= 1:
                return f"{gb:.1f} GB"
            mb = bytes_val / (1024**2)
            return f"{mb:.0f} MB"

        def get_disk_status(path: Optional[Path], name: str) -> str:
            if not path or not path.exists():
                return f"- {name}: Not found"

            try:
                import shutil
                usage = shutil.disk_usage(str(path))
                free = format_size(usage.free)
                total = format_size(usage.total)
                percent_used = (usage.used / usage.total) * 100

                # Warning thresholds
                if usage.free < 10 * 1024**3 or percent_used > 90:
                    icon = "Warning"
                elif usage.free < 50 * 1024**3:
                    icon = "Low"
                else:
                    icon = "OK"

                return f"- {name}: {icon} - {free} free / {total}"
            except Exception as e:
                return f"- {name}: Error: {e}"

        lines = []

        # Models path (ComfyUI)
        if self._models_path:
            lines.append(get_disk_status(self._models_path, f"Models ({self._models_path})"))
        else:
            lines.append("- Models: Not configured")

        # Backup path
        if self._backup_path:
            lines.append(get_disk_status(self._backup_path, f"Backup ({self._backup_path})"))

        # Environment-specific
        if os.path.exists("/workspace"):
            lines.append(get_disk_status(Path("/workspace"), "Workspace"))
        if os.path.exists("/runpod-volume"):
            lines.append(get_disk_status(Path("/runpod-volume"), "Volume"))

        return "\n".join(lines)

    def get_workflows(self) -> List[Tuple[str, str]]:
        """Get list of workflows with model definitions."""
        result = []
        for wf_id, wf_data in self._workflow_models.get("workflows", {}).items():
            name = wf_data.get("name", wf_id)
            category = wf_data.get("category", "")
            result.append((f"{name} ({category})", wf_id))
        return sorted(result, key=lambda x: x[0])

    def get_vram_tiers_for_workflow(self, workflow_id: str) -> List[str]:
        """Get available VRAM tiers for a workflow."""
        wf = self._workflow_models.get("workflows", {}).get(workflow_id, {})
        model_sets = wf.get("model_sets", {})

        available_tiers = set()
        for set_name, set_data in model_sets.items():
            vram = set_data.get("vram_gb", 0)
            for tier, tier_vrams in self.VRAM_TIERS.items():
                if vram in tier_vrams:
                    available_tiers.add(tier)

        return sorted(available_tiers)

    def get_models_for_workflow_tier(
        self, workflow_id: str, tier: str
    ) -> List[ModelInfo]:
        """Get models for a workflow and VRAM tier."""
        wf = self._workflow_models.get("workflows", {}).get(workflow_id, {})
        model_sets = wf.get("model_sets", {})
        all_models = self._workflow_models.get("models", {})

        tier_vrams = self.VRAM_TIERS.get(tier, [])

        model_ids = set()
        for set_name, set_data in model_sets.items():
            vram = set_data.get("vram_gb", 0)
            if vram in tier_vrams:
                model_ids.update(set_data.get("models", []))

        result = []
        for mid in sorted(model_ids):
            m_data = all_models.get(mid, {})
            model = ModelInfo(
                id=mid,
                filename=m_data.get("filename", mid),
                url=m_data.get("url", ""),
                size_mb=m_data.get("size_mb", 0),
                target_path=m_data.get("target_path", ""),
            )
            self._check_model_status(model)
            result.append(model)

        return result

    def _check_model_status(self, model: ModelInfo) -> None:
        """Check model status in ComfyUI and backup."""
        model.status = ModelStatus.MISSING
        model.comfy_size = 0
        model.backup_size = 0

        if model.filename in self._download_progress:
            model.status = ModelStatus.DOWNLOADING
            return

        if self._models_path:
            comfy_file = self._models_path / model.target_path / model.filename
            if comfy_file.exists():
                model.comfy_size = comfy_file.stat().st_size
                model.status = ModelStatus.PRESENT

        if self._backup_path:
            backup_file = self._backup_path / model.target_path / model.filename
            if backup_file.exists():
                model.backup_size = backup_file.stat().st_size
                if model.status == ModelStatus.MISSING:
                    model.status = ModelStatus.BACKUP_ONLY

    def get_models_table(self, workflow_id: str, tier: str) -> List[List[Any]]:
        """Get models as table data: [Status, Dateiname, Ordner, MB, Aktion]"""
        models = self.get_models_for_workflow_tier(workflow_id, tier)

        table = []
        for m in models:
            status_icon = {
                ModelStatus.PRESENT: "✅",
                ModelStatus.MISSING: "❌",
                ModelStatus.BACKUP_ONLY: "📦",
                ModelStatus.DOWNLOADING: "⬇️",
                ModelStatus.ERROR: "⚠️",
            }.get(m.status, "?")

            action = ""
            if m.status == ModelStatus.MISSING:
                action = "Download"
            elif m.status == ModelStatus.BACKUP_ONLY:
                action = "Restore"
            elif m.status == ModelStatus.PRESENT:
                action = "Cleanup"

            table.append([
                status_icon,
                m.filename,
                m.target_path,
                m.size_mb,
                action,
            ])

        return table

    def _get_ssl_context(self):
        """Get SSL context based on config (secure by default)."""
        import ssl

        # Check config for SSL bypass (INSECURE - use only if needed)
        disable_ssl = self._config.get("security", {}).get("disable_ssl_verify", False)

        if disable_ssl:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return ctx

        # Default: secure SSL verification
        return ssl.create_default_context()

    def download_model(self, model_id: str) -> str:
        """Download a model to ComfyUI/models + backup."""
        models_data = self._workflow_models.get("models", {})
        if model_id not in models_data:
            return f"Model {model_id} not found"

        m_data = models_data[model_id]
        filename = m_data.get("filename", "")
        url = m_data.get("url", "")
        target_path = m_data.get("target_path", "")

        if not url:
            return f"No URL for {filename}"

        if not self._models_path:
            return "ComfyUI models path not configured"

        # Security: Validate target_path is in allowed folders
        if target_path not in self.ALLOWED_FOLDERS:
            # Check if it's a subfolder of an allowed folder
            allowed = False
            for folder in self.ALLOWED_FOLDERS:
                if target_path.startswith(folder + "/") or target_path == folder:
                    allowed = True
                    break
            if not allowed:
                return f"Security: Invalid target folder '{target_path}'"

        # Security: Sanitize and validate paths
        target_file = _sanitize_path(self._models_path, target_path, filename)
        if not target_file:
            return f"Security: Invalid path for {filename}"

        # Create target directory
        target_file.parent.mkdir(parents=True, exist_ok=True)

        # Backup path (also sanitized)
        backup_file = None
        if self._backup_path:
            backup_file = _sanitize_path(self._backup_path, target_path, filename)
            if backup_file:
                backup_file.parent.mkdir(parents=True, exist_ok=True)

        def download_thread():
            import urllib.request

            try:
                self._download_progress[filename] = 0.0
                self._download_status[filename] = "Starting..."

                ctx = self._get_ssl_context()
                req = urllib.request.Request(url, headers={"User-Agent": "CindergaceToolkit/3.0"})

                with urllib.request.urlopen(req, context=ctx, timeout=60) as response:
                    total_size = int(response.headers.get("Content-Length", 0))
                    downloaded = 0
                    chunk_size = 1024 * 1024

                    with open(target_file, "wb") as f:
                        while True:
                            chunk = response.read(chunk_size)
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)

                            if total_size > 0:
                                progress = downloaded / total_size
                                self._download_progress[filename] = progress
                                mb_done = downloaded / (1024 * 1024)
                                mb_total = total_size / (1024 * 1024)
                                self._download_status[filename] = f"⬇️ {mb_done:.0f}/{mb_total:.0f} MB"

                if backup_file:
                    self._download_status[filename] = "Backing up..."
                    shutil.copy2(target_file, backup_file)

                del self._download_progress[filename]
                self._download_status[filename] = "Done"

            except Exception as e:
                self._download_status[filename] = f"❌ {str(e)[:50]}"
                if target_file.exists():
                    target_file.unlink()

        thread = threading.Thread(target=download_thread, daemon=True)
        thread.start()
        return f"Download started: {filename}"

    def restore_from_backup(self, model_id: str) -> str:
        """Restore a model from backup to ComfyUI."""
        models_data = self._workflow_models.get("models", {})
        if model_id not in models_data:
            return "Model not found"

        m_data = models_data[model_id]
        filename = m_data.get("filename", "")
        target_path = m_data.get("target_path", "")

        if not self._backup_path or not self._models_path:
            return "Paths not configured"

        # Security: Validate target_path is in allowed folders
        if not self._is_allowed_folder(target_path):
            return f"Security: Invalid target folder '{target_path}'"

        # Security: Sanitize paths
        backup_file = _sanitize_path(self._backup_path, target_path, filename)
        if not backup_file:
            return f"Security: Invalid backup path for {filename}"

        if not backup_file.exists():
            return f"{filename} not in backup"

        target_file = _sanitize_path(self._models_path, target_path, filename)
        if not target_file:
            return f"Security: Invalid target path for {filename}"

        target_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup_file, target_file)
        return f"Restored: {filename}"

    def find_other_models(self, workflow_id: str, tier: str) -> List[Tuple[str, str, int]]:
        """Find models in ComfyUI that are NOT part of the selected workflow/tier.

        Returns: [(filename, target_path, size_mb), ...]
        """
        if not self._models_path:
            return []

        # Get expected models for this workflow/tier
        expected = set()
        models = self.get_models_for_workflow_tier(workflow_id, tier)
        for m in models:
            expected.add((m.target_path, m.filename))

        # Scan ComfyUI/models for all model files
        other_models = []
        model_extensions = {".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf"}

        for folder in self._workflow_models.get("target_folders", []):
            # Security: Only scan folders in the allowlist
            if not self._is_allowed_folder(folder):
                continue

            folder_path = self._models_path / folder
            if not folder_path.exists():
                continue

            for file in folder_path.iterdir():
                if file.is_file() and file.suffix.lower() in model_extensions:
                    if (folder, file.name) not in expected:
                        size_mb = file.stat().st_size // (1024 * 1024)
                        other_models.append((file.name, folder, size_mb))

        return sorted(other_models)

    def delete_other_models(self, filenames: List[Tuple[str, str]]) -> List[str]:
        """Delete other models (with backup if configured).

        Args:
            filenames: List of (filename, target_path) tuples

        Returns:
            List of status messages
        """
        results = []

        for filename, target_path in filenames:
            if not self._models_path:
                results.append("No models path")
                continue

            # Security: Sanitize paths
            source_file = _sanitize_path(self._models_path, target_path, filename)
            if not source_file:
                results.append(f"Security: Invalid path for {filename}")
                continue

            if not source_file.exists():
                results.append(f"{filename} not found")
                continue

            source_size = source_file.stat().st_size

            if self._backup_path:
                backup_file = _sanitize_path(self._backup_path, target_path, filename)
                if not backup_file:
                    # Can't backup, just delete
                    source_file.unlink()
                    results.append(f"Deleted {filename} (no backup possible)")
                    continue

                if backup_file.exists():
                    backup_size = backup_file.stat().st_size
                    if source_size == backup_size:
                        source_file.unlink()
                        results.append(f"Deleted {filename} (in backup)")
                    else:
                        # Move and overwrite
                        backup_file.parent.mkdir(parents=True, exist_ok=True)
                        backup_file.unlink()
                        shutil.move(str(source_file), str(backup_file))
                        results.append(f"Moved {filename} (backup updated)")
                else:
                    backup_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(source_file), str(backup_file))
                    results.append(f"Moved {filename} to backup")
            else:
                source_file.unlink()
                results.append(f"Deleted {filename}")

        return results

    def render(self) -> gr.Blocks:
        """Render the Model Depot UI."""

        with gr.Blocks() as ui:
            gr.Markdown("## 📦 Model Depot")

            # === Workflow + Tier Selection ===
            with gr.Row():
                wf_choices = self.get_workflows()
                workflow_dropdown = gr.Dropdown(
                    label="Workflow",
                    choices=wf_choices,
                    value=None,
                    scale=2,
                )
                tier_dropdown = gr.Dropdown(
                    label="VRAM Tier (S=8-12, M=16, L=24-32 GB)",
                    choices=[],
                    value=None,
                    scale=1,
                )

            # === Models Table ===
            models_table = gr.Dataframe(
                headers=["Status", "Filename", "Folder", "MB", "Action"],
                datatype=["str", "str", "str", "number", "str"],
                label="Models",
                interactive=False,
            )

            # === Actions ===
            with gr.Row():
                download_all_btn = gr.Button("Download All Missing", variant="primary", scale=2)
                refresh_btn = gr.Button("Refresh", scale=1)

            status_output = gr.Textbox(label="Status", lines=3, interactive=False)

            # Auto-refresh timer (every 3 seconds while downloads active)
            auto_refresh_timer = gr.Timer(value=3, active=False)

            gr.Markdown("---")

            # === Delete Other Models (visible by default) ===
            gr.Markdown("### Delete Other Models")
            gr.Markdown("*Models in ComfyUI/models that are NOT part of the selected workflow/tier*")

            other_models_table = gr.Dataframe(
                headers=["Filename", "Folder", "MB"],
                datatype=["str", "str", "number"],
                label="Other Models",
                interactive=False,
            )

            scan_other_btn = gr.Button("Scan for Other Models")

            with gr.Row():
                delete_other_checkbox = gr.Checkbox(
                    label="Yes, delete other models",
                    value=False,
                )
                delete_other_btn = gr.Button(
                    "Delete",
                    variant="stop",
                    interactive=False,
                )

            # Safety confirmation
            with gr.Group(visible=False) as safety_group:
                safety_info = gr.Markdown("")
                with gr.Row():
                    safety_confirm_btn = gr.Button("Yes, really delete", variant="stop")
                    safety_cancel_btn = gr.Button("Cancel")

            other_status = gr.Textbox(label="Status", lines=3, interactive=False)

            gr.Markdown("---")

            # === Config Info ===
            with gr.Accordion("Data Sources & Storage", open=True):
                env_name = "runpod" if os.path.exists("/workspace") else ("colab" if os.path.exists("/content") else "local")
                config_info = f"**Environment:** `{env_name}`\n\n"
                config_info += f"**Config:** `{self._config_source or 'none'}`\n\n"
                config_info += f"**Models JSON:** `{self._models_source}`\n\n"

                # Disk info
                disk_info = self._get_disk_info()
                config_info += f"**Storage:**\n{disk_info}"

                gr.Markdown(config_info)

            # === State ===
            current_workflow = gr.State(value=None)
            current_tier = gr.State(value=None)
            other_models_state = gr.State(value=[])

            # === Event Handlers ===

            def on_workflow_change(wf_id):
                if not wf_id:
                    return gr.update(choices=[], value=None), [], wf_id

                # Reload data to get latest changes from Workflow Manager
                self._load_workflow_models()

                tiers = self.get_vram_tiers_for_workflow(wf_id)
                tier_choices = [(f"{t} ({'/'.join(str(v) for v in self.VRAM_TIERS[t])}GB)", t) for t in tiers]

                return (
                    gr.update(choices=tier_choices, value=tiers[0] if tiers else None),
                    [],
                    wf_id,
                )

            def on_tier_change(wf_id, tier):
                if not wf_id or not tier:
                    return [], tier

                table = self.get_models_table(wf_id, tier)
                return table, tier

            def on_download_all(wf_id, tier):
                if not wf_id or not tier:
                    return "Select workflow/tier first", gr.update(active=False)

                models = self.get_models_for_workflow_tier(wf_id, tier)
                started = []

                for m in models:
                    if m.status == ModelStatus.MISSING:
                        msg = self.download_model(m.id)
                        started.append(msg)
                    elif m.status == ModelStatus.BACKUP_ONLY:
                        msg = self.restore_from_backup(m.id)
                        started.append(msg)

                if not started:
                    return "All models already present", gr.update(active=False)

                # Activate auto-refresh timer
                return "\n".join(started), gr.update(active=True)

            def on_refresh(wf_id, tier):
                if not wf_id or not tier:
                    return [], "", gr.update(active=False)

                # Reload workflow_models.json to get latest changes
                self._load_workflow_models()

                table = self.get_models_table(wf_id, tier)

                status_lines = []
                downloads_active = False
                for fn, status in self._download_status.items():
                    status_lines.append(f"{fn}: {status}")
                    if fn in self._download_progress:
                        downloads_active = True

                # Deactivate timer if no downloads running
                timer_update = gr.update(active=downloads_active)
                return table, "\n".join(status_lines) if status_lines else "Data refreshed", timer_update

            def on_auto_refresh(wf_id, tier):
                """Auto-refresh triggered by timer."""
                if not wf_id or not tier:
                    return [], "", gr.update(active=False)

                table = self.get_models_table(wf_id, tier)

                status_lines = []
                downloads_active = bool(self._download_progress)
                for fn, status in self._download_status.items():
                    status_lines.append(f"{fn}: {status}")

                # Deactivate timer if no downloads running
                timer_update = gr.update(active=downloads_active)
                return table, "\n".join(status_lines) if status_lines else "", timer_update

            def on_scan_other(wf_id, tier):
                if not wf_id or not tier:
                    return [], [], "Select workflow/tier first"

                other = self.find_other_models(wf_id, tier)
                table = [[fn, path, mb] for fn, path, mb in other]
                total_mb = sum(mb for _, _, mb in other)

                return table, other, f"Found: {len(other)} files ({total_mb} MB)"

            def on_delete_checkbox_change(checked):
                return gr.update(interactive=checked)

            def on_delete_other_click(other_models):
                if not other_models:
                    return gr.update(visible=False), "", ""

                count = len(other_models)
                total_mb = sum(mb for _, _, mb in other_models)
                info = f"**{count} files ({total_mb} MB) will be deleted!**\n\n"
                info += "This action cannot be undone.\n"
                info += "Are you sure?"

                return gr.update(visible=True), info, ""

            def on_safety_confirm(other_models, wf_id, tier):
                if not other_models:
                    return gr.update(visible=False), "", [], []

                filenames = [(fn, path) for fn, path, _ in other_models]
                results = self.delete_other_models(filenames)

                # Refresh other models list
                new_other = self.find_other_models(wf_id, tier) if wf_id and tier else []
                new_table = [[fn, path, mb] for fn, path, mb in new_other]

                return (
                    gr.update(visible=False),
                    "\n".join(results),
                    new_table,
                    new_other,
                )

            def on_safety_cancel():
                return gr.update(visible=False), "Cancelled"

            # === Wire Events ===
            workflow_dropdown.change(
                on_workflow_change,
                inputs=[workflow_dropdown],
                outputs=[tier_dropdown, models_table, current_workflow],
            )

            tier_dropdown.change(
                on_tier_change,
                inputs=[current_workflow, tier_dropdown],
                outputs=[models_table, current_tier],
            )

            download_all_btn.click(
                on_download_all,
                inputs=[current_workflow, current_tier],
                outputs=[status_output, auto_refresh_timer],
            )

            refresh_btn.click(
                on_refresh,
                inputs=[current_workflow, current_tier],
                outputs=[models_table, status_output, auto_refresh_timer],
            )

            auto_refresh_timer.tick(
                on_auto_refresh,
                inputs=[current_workflow, current_tier],
                outputs=[models_table, status_output, auto_refresh_timer],
            )

            scan_other_btn.click(
                on_scan_other,
                inputs=[current_workflow, current_tier],
                outputs=[other_models_table, other_models_state, other_status],
            )

            delete_other_checkbox.change(
                on_delete_checkbox_change,
                inputs=[delete_other_checkbox],
                outputs=[delete_other_btn],
            )

            delete_other_btn.click(
                on_delete_other_click,
                inputs=[other_models_state],
                outputs=[safety_group, safety_info, other_status],
            )

            safety_confirm_btn.click(
                on_safety_confirm,
                inputs=[other_models_state, current_workflow, current_tier],
                outputs=[safety_group, other_status, other_models_table, other_models_state],
            )

            safety_cancel_btn.click(
                on_safety_cancel,
                outputs=[safety_group, other_status],
            )

        return ui
