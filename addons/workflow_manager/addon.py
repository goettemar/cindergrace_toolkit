"""Workflow Manager Addon - Create and manage workflow model definitions."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import gradio as gr

from core.base_addon import BaseAddon
from .workflow_parser import parse_workflow
from .url_database import suggest_url


class WorkflowManagerAddon(BaseAddon):
    """Workflow Manager with VRAM checkboxes and folder dropdown."""

    PROJECT_DIR = Path(__file__).parent.parent.parent
    USER_CONFIG_DIR = PROJECT_DIR / ".config"
    DATA_DIR = PROJECT_DIR / "data"
    CONFIG_DIR = PROJECT_DIR / "config"

    # VRAM tiers: S=Small(8-12GB), M=Medium(16GB), L=Large(24-32GB)
    VRAM_TIERS = {"S": [8, 12], "M": [16], "L": [24, 32]}

    # Allowed target folders (shared with Model Depot for consistency)
    ALLOWED_FOLDERS = {
        "checkpoints", "clip_vision", "controlnet", "diffusion_models",
        "diffusion_models/wan", "loras", "loras/wan", "text_encoders",
        "upscale_models", "vae", "LLM"
    }

    def __init__(self):
        super().__init__()
        self.name = "Workflow Manager"
        self.version = "5.1.0"
        self.icon = "📋"

        self._config: Dict[str, Any] = {}
        self._workflow_models: Dict[str, Any] = {}
        self._workflows_path: Optional[Path] = None

    def get_tab_name(self) -> str:
        return f"{self.icon} {self.name}"

    def on_load(self) -> None:
        self._load_config()
        self._load_workflow_models()
        self._detect_paths()

    def _load_config(self) -> None:
        user_file = self.USER_CONFIG_DIR / "config.json"
        default_file = self.CONFIG_DIR / "config.json"

        if user_file.exists():
            with open(user_file, "r", encoding="utf-8") as f:
                self._config = json.load(f)
        elif default_file.exists():
            with open(default_file, "r", encoding="utf-8") as f:
                self._config = json.load(f)

    def _load_workflow_models(self) -> None:
        """Load workflow_models.json from data/ (Git source only)."""
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

    def _save_workflow_models(self) -> str:
        """Save workflow_models directly to data/ (Git source)."""
        git_file = self.DATA_DIR / "workflow_models.json"
        with open(git_file, "w", encoding="utf-8") as f:
            json.dump(self._workflow_models, f, indent=2, ensure_ascii=False)

        return "Saved (data/workflow_models.json)"

    def _detect_paths(self) -> None:
        import os
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

            wf_template = paths_config.get("workflows", {}).get(env, "{comfyui}/user/default/workflows")
            wf_path = wf_template.replace("{comfyui}", comfy_path)
            if os.path.exists(wf_path):
                self._workflows_path = Path(wf_path)

    def get_target_folders(self) -> List[str]:
        """Get list of target folders from JSON."""
        return self._workflow_models.get("target_folders", [])

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

    def add_target_folder(self, folder: str) -> Tuple[str, List[str]]:
        """Add a new target folder."""
        folder = folder.strip()
        if not folder:
            return "Folder name required", self.get_target_folders()

        # Security: Validate against allowlist
        if not self._is_allowed_folder(folder):
            allowed = ", ".join(sorted(self.ALLOWED_FOLDERS))
            return f"Security: '{folder}' not allowed. Valid: {allowed}", self.get_target_folders()

        folders = self._workflow_models.get("target_folders", [])
        if folder not in folders:
            folders.append(folder)
            folders.sort()
            self._workflow_models["target_folders"] = folders
            self._save_workflow_models()
            return f"Added '{folder}'", folders
        return f"'{folder}' already exists", folders

    def remove_target_folder(self, folder: str) -> Tuple[str, List[str]]:
        """Remove a target folder."""
        folders = self._workflow_models.get("target_folders", [])
        if folder in folders:
            folders.remove(folder)
            self._workflow_models["target_folders"] = folders
            self._save_workflow_models()
            return f"Removed '{folder}'", folders
        return f"'{folder}' not found", folders

    def scan_workflows(self) -> List[Tuple[str, bool]]:
        """Scan local workflows and check if in JSON."""
        if not self._workflows_path:
            return []

        pattern = self._config.get("workflow_pattern", "gc*.json")
        result = []

        for wf_file in self._workflows_path.glob(pattern):
            wf_id = wf_file.stem
            is_in_json = wf_id in self._workflow_models.get("workflows", {})
            result.append((wf_id, is_in_json))

        return sorted(result, key=lambda x: (not x[1], x[0]))

    def get_models_table(self, workflow_id: str) -> List[List[Any]]:
        """Get models table for a workflow.

        Returns: [Dateiname, Ordner, MB, S, M, L, URL]
        S=8-12GB, M=16GB, L=24-32GB
        """
        wf = self._workflow_models.get("workflows", {}).get(workflow_id, {})
        model_sets = wf.get("model_sets", {})
        all_models = self._workflow_models.get("models", {})

        if not model_sets:
            return []

        # Collect model_ids and their VRAM assignments
        model_vram_map = {}  # model_id -> set of VRAM values

        for set_name, set_data in model_sets.items():
            vram = set_data.get("vram_gb", 0)
            for mid in set_data.get("models", []):
                if mid not in model_vram_map:
                    model_vram_map[mid] = set()
                model_vram_map[mid].add(vram)

        # Build table
        table = []
        for mid in sorted(model_vram_map.keys()):
            model = all_models.get(mid, {})
            vrams = model_vram_map[mid]

            row = [
                model.get("filename", mid),
                model.get("target_path", ""),
                model.get("size_mb", 0),
            ]
            # Add VRAM tier checkboxes (S, M, L)
            for tier, tier_vrams in self.VRAM_TIERS.items():
                row.append(any(v in vrams for v in tier_vrams))
            row.append(model.get("url", ""))
            table.append(row)

        return table

    def parse_workflow_to_table(self, workflow_id: str) -> List[List[Any]]:
        """Parse workflow and return table with URL suggestions."""
        if not self._workflows_path:
            return []

        wf_path = self._workflows_path / f"{workflow_id}.json"
        parsed_models = parse_workflow(wf_path)

        table = []
        for pm in parsed_models:
            known = suggest_url(pm.filename)
            row = [
                pm.filename,
                pm.target_path,
                known.size_mb if known else 0,
            ]
            # Default: all tiers checked (S, M, L)
            for _ in self.VRAM_TIERS:
                row.append(True)
            row.append(known.url if known else "")
            table.append(row)

        return table

    def save_workflow(
        self,
        workflow_id: str,
        table_data: List[List[Any]],
    ) -> str:
        """Save workflow from table data."""
        if not workflow_id:
            return "No workflow selected"

        # Ensure structures exist
        if "workflows" not in self._workflow_models:
            self._workflow_models["workflows"] = {}
        if "models" not in self._workflow_models:
            self._workflow_models["models"] = {}

        # Create/update workflow
        if workflow_id not in self._workflow_models["workflows"]:
            self._workflow_models["workflows"][workflow_id] = {
                "name": workflow_id,
                "description": "",
                "category": "video" if "gcv" in workflow_id else "image",
                "model_sets": {},
            }

        wf = self._workflow_models["workflows"][workflow_id]
        wf["model_sets"] = {}

        # Table format: [filename, folder, mb, S, M, L, url]
        # S=8-12GB, M=16GB, L=24-32GB
        tier_to_models = {tier: [] for tier in self.VRAM_TIERS}

        for row in table_data:
            if len(row) < 7 or not row[0]:
                continue

            filename = str(row[0]).strip()
            target_path = str(row[1]).strip() if row[1] else ""
            size_mb = int(row[2]) if row[2] else 0

            # VRAM tier checkboxes at index 3-5 (S, M, L)
            tier_checks = row[3:6]
            url = str(row[6]).strip() if len(row) > 6 and row[6] else ""

            if not filename:
                continue

            # Generate model_id with collision detection
            base_model_id = filename.replace(".", "_").replace("-", "_").lower()
            model_id = base_model_id

            # Check for collision - if existing model has different filename, add suffix
            existing = self._workflow_models["models"].get(model_id)
            if existing and existing.get("filename") != filename:
                # Collision detected - append target_path hash to make unique
                suffix = target_path.replace("/", "_").replace(".", "_")
                model_id = f"{base_model_id}_{suffix}"

            # Save model definition
            self._workflow_models["models"][model_id] = {
                "name": filename,
                "filename": filename,
                "url": url,
                "target_path": target_path,
                "size_mb": size_mb,
            }

            # Add to tier sets based on checkboxes
            for i, tier in enumerate(self.VRAM_TIERS.keys()):
                if i < len(tier_checks) and tier_checks[i]:
                    tier_to_models[tier].append(model_id)

        # Create model sets - expand tiers to actual VRAM values
        for tier, model_ids in tier_to_models.items():
            if model_ids:
                vram_values = self.VRAM_TIERS[tier]
                for vram in vram_values:
                    set_name = f"{vram}GB"
                    wf["model_sets"][set_name] = {
                        "name": f"{vram}GB VRAM",
                        "vram_gb": vram,
                        "models": model_ids,
                    }

        return self._save_workflow_models()

    def render(self) -> gr.Blocks:
        """Render the Workflow Manager UI."""

        # Table: Filename | Folder | MB | S | M | L | URL
        # S=8-12GB, M=16GB, L=24-32GB
        headers = ["Filename", "Folder", "MB", "S", "M", "L", "URL"]
        datatypes = ["str", "str", "number", "bool", "bool", "bool", "str"]

        with gr.Blocks() as ui:
            gr.Markdown("## 📋 Workflow Manager")

            # === Workflow Selection ===
            with gr.Row():
                workflow_list = self.scan_workflows()
                wf_choices = [(f"{'✅' if in_json else '⚠️'} {wf_id}", wf_id)
                              for wf_id, in_json in workflow_list]

                workflow_dropdown = gr.Dropdown(
                    label="Workflow",
                    choices=wf_choices,
                    value=None,
                    scale=3,
                )
                scan_btn = gr.Button("🔄", scale=0, min_width=50)

            # === Action buttons together ===
            with gr.Row():
                parse_btn = gr.Button("Auto-Parse", scale=1)
                load_btn = gr.Button("Load", scale=1)
                add_row_btn = gr.Button("Add Row", scale=1)
                del_row_btn = gr.Button("Delete Last", variant="stop", scale=1)

            # === Models Table ===
            models_table = gr.Dataframe(
                headers=headers,
                datatype=datatypes,
                column_count=(7, "fixed"),
                row_count=(5, "dynamic"),
                label="Models",
                interactive=True,
                wrap=True,
            )

            gr.Markdown("*S=8-12GB, M=16GB, L=24-32GB*")

            # === Save ===
            with gr.Row():
                save_btn = gr.Button("Save", variant="primary")

            status_output = gr.Textbox(label="Status", lines=1, interactive=False)

            gr.Markdown("---")

            # === Target Folders Management ===
            with gr.Accordion("Target Folders", open=False):
                gr.Markdown("*These folders are available as model targets:*")

                folders_list = gr.Dataframe(
                    headers=["Folder"],
                    datatype=["str"],
                    value=[[f] for f in self.get_target_folders()],
                    row_count=(5, "dynamic"),
                    interactive=False,
                )

                with gr.Row():
                    new_folder_input = gr.Textbox(
                        label="New Folder",
                        placeholder="e.g. loras/sdxl",
                        scale=2,
                    )
                    add_folder_btn = gr.Button("Add", scale=1)

                with gr.Row():
                    del_folder_dropdown = gr.Dropdown(
                        label="Remove Folder",
                        choices=self.get_target_folders(),
                        scale=2,
                    )
                    del_folder_btn = gr.Button("Remove", variant="stop", scale=1)

                folder_status = gr.Textbox(label="", lines=1, interactive=False)

            # === State ===
            current_workflow = gr.State(value=None)

            # === Event Handlers ===

            def on_scan():
                workflow_list = self.scan_workflows()
                choices = [(f"{'✅' if in_json else '⚠️'} {wf_id}", wf_id)
                           for wf_id, in_json in workflow_list]
                return gr.update(choices=choices)

            def on_workflow_select(wf_id):
                if not wf_id:
                    return [], wf_id

                table = self.get_models_table(wf_id)
                if not table:
                    table = self.parse_workflow_to_table(wf_id)

                return table, wf_id

            def on_parse(wf_id):
                if not wf_id:
                    return []
                return self.parse_workflow_to_table(wf_id)

            def on_load(wf_id):
                if not wf_id:
                    return []
                return self.get_models_table(wf_id)

            def on_add_row(table_data):
                if hasattr(table_data, 'values'):
                    table_data = table_data.values.tolist()
                if table_data is None:
                    table_data = []
                # New row: [filename, folder, mb, S, M, L, url]
                new_row = ["", "", 0, True, True, True, ""]
                table_data.append(new_row)
                return table_data

            def on_del_row(table_data):
                if hasattr(table_data, 'values'):
                    table_data = table_data.values.tolist()
                if table_data and len(table_data) > 0:
                    table_data.pop()
                return table_data

            def on_save(wf_id, table_data):
                if hasattr(table_data, 'values'):
                    table_data = table_data.values.tolist()
                return self.save_workflow(wf_id, table_data)

            def on_add_folder(folder_name):
                msg, folders = self.add_target_folder(folder_name)
                return (
                    msg,
                    [[f] for f in folders],
                    gr.update(choices=folders),
                    "",
                )

            def on_del_folder(folder_name):
                msg, folders = self.remove_target_folder(folder_name)
                return (
                    msg,
                    [[f] for f in folders],
                    gr.update(choices=folders, value=None),
                )

            # === Wire Events ===
            scan_btn.click(on_scan, outputs=[workflow_dropdown])

            workflow_dropdown.change(
                on_workflow_select,
                inputs=[workflow_dropdown],
                outputs=[models_table, current_workflow],
            )

            parse_btn.click(on_parse, inputs=[current_workflow], outputs=[models_table])
            load_btn.click(on_load, inputs=[current_workflow], outputs=[models_table])
            add_row_btn.click(on_add_row, inputs=[models_table], outputs=[models_table])
            del_row_btn.click(on_del_row, inputs=[models_table], outputs=[models_table])

            save_btn.click(
                on_save,
                inputs=[current_workflow, models_table],
                outputs=[status_output],
            )

            add_folder_btn.click(
                on_add_folder,
                inputs=[new_folder_input],
                outputs=[folder_status, folders_list, del_folder_dropdown, new_folder_input],
            )

            del_folder_btn.click(
                on_del_folder,
                inputs=[del_folder_dropdown],
                outputs=[folder_status, folders_list, del_folder_dropdown],
            )

        return ui
