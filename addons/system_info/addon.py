"""System Info Addon - Display GPU, memory and disk information."""

import os
import subprocess
import sys
from pathlib import Path

import gradio as gr

from core.base_addon import BaseAddon


PROJECT_DIR = Path(__file__).parent.parent.parent


class SystemInfoAddon(BaseAddon):
    """Addon to display system information.

    Shows:
    - GPU info (nvidia-smi)
    - Memory usage
    - Disk space
    - Environment detection (RunPod/Colab/Local)
    """

    def __init__(self):
        super().__init__()
        self.name = "System Info"
        self.version = "1.0.0"
        self.icon = "💻"

    def get_tab_name(self) -> str:
        return f"{self.icon} {self.name}"

    def get_gpu_info(self) -> str:
        """Get GPU information using nvidia-smi."""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free,temperature.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                output = "### GPU Information\n\n"
                for i, line in enumerate(lines):
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 5:
                        name, total, used, free, temp = parts[:5]
                        output += f"**GPU {i}:** {name}\n"
                        output += f"- VRAM: {used} MB / {total} MB (frei: {free} MB)\n"
                        output += f"- Temperatur: {temp}°C\n\n"
                return output
            return "nvidia-smi nicht verfügbar"
        except Exception as e:
            return f"GPU Info Fehler: {e}"

    def get_memory_info(self) -> str:
        """Get system memory information."""
        try:
            with open("/proc/meminfo", "r") as f:
                lines = f.readlines()

            mem_info = {}
            for line in lines:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip().split()[0]
                    mem_info[key] = int(value)

            total_gb = mem_info.get("MemTotal", 0) / 1024 / 1024
            free_gb = mem_info.get("MemAvailable", mem_info.get("MemFree", 0)) / 1024 / 1024
            used_gb = total_gb - free_gb

            output = "### RAM\n\n"
            output += f"- Gesamt: {total_gb:.1f} GB\n"
            output += f"- Verwendet: {used_gb:.1f} GB\n"
            output += f"- Verfügbar: {free_gb:.1f} GB\n"
            return output

        except Exception as e:
            return f"Memory Info Fehler: {e}"

    def get_disk_info(self) -> str:
        """Get disk space information."""
        try:
            # Only show paths that exist
            paths_to_check = []

            if os.path.exists("/workspace"):
                paths_to_check.append(("/workspace", "Workspace"))
            if os.path.exists("/content"):
                paths_to_check.append(("/content", "Colab Content"))
            if not paths_to_check:
                paths_to_check.append((str(Path.home()), "Home"))

            output = "### Speicherplatz\n\n"

            for path, label in paths_to_check:
                stat = os.statvfs(path)
                total_gb = (stat.f_blocks * stat.f_frsize) / (1024**3)
                free_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
                used_gb = total_gb - free_gb
                percent = (used_gb / total_gb * 100) if total_gb > 0 else 0

                output += f"**{label}** (`{path}`)\n"
                output += f"- {used_gb:.1f} GB / {total_gb:.1f} GB ({percent:.0f}%)\n"
                output += f"- Frei: {free_gb:.1f} GB\n\n"

            return output if len(output) > 30 else "Keine Laufwerke gefunden"

        except Exception as e:
            return f"Disk Info Fehler: {e}"

    def get_environment(self) -> str:
        """Detect current environment."""
        output = "### Umgebung\n\n"

        if os.environ.get("RUNPOD_POD_ID") or (os.path.exists("/workspace") and not os.path.exists("/content")):
            output += "**Plattform:** 🚀 RunPod\n"
            pod_id = os.environ.get("RUNPOD_POD_ID", "unbekannt")
            output += f"- Pod ID: `{pod_id}`\n"
        elif os.path.exists("/content") and "COLAB_GPU" in os.environ:
            output += "**Plattform:** 📓 Google Colab\n"
        else:
            output += "**Plattform:** 🖥️ Lokal\n"

        output += f"- Python: {sys.version.split()[0]}\n"

        cuda_version = os.environ.get("CUDA_VERSION", "unbekannt")
        output += f"- CUDA: {cuda_version}\n"

        return output

    def get_toolkit_info(self) -> str:
        """Get toolkit version and git status."""
        output = "### Toolkit\n\n"

        try:
            # Get current commit
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=PROJECT_DIR,
                capture_output=True,
                text=True,
                timeout=10,
            )
            commit = result.stdout.strip() if result.returncode == 0 else "unknown"

            # Get branch
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=PROJECT_DIR,
                capture_output=True,
                text=True,
                timeout=10,
            )
            branch = result.stdout.strip() if result.returncode == 0 else "unknown"

            output += f"- Branch: `{branch}`\n"
            output += f"- Commit: `{commit}`\n"

            # Check for updates
            subprocess.run(
                ["git", "fetch", "--quiet"],
                cwd=PROJECT_DIR,
                capture_output=True,
                timeout=30,
            )

            result = subprocess.run(
                ["git", "status", "-uno"],
                cwd=PROJECT_DIR,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if "behind" in result.stdout:
                output += "- Status: ⚠️ **Update verfügbar**\n"
            else:
                output += "- Status: ✅ Aktuell\n"

        except Exception as e:
            output += f"- Error: {e}\n"

        return output

    def upgrade_toolkit(self) -> str:
        """Pull latest changes from git."""
        try:
            result = subprocess.run(
                ["git", "pull", "--ff-only"],
                cwd=PROJECT_DIR,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                return f"✅ Update erfolgreich:\n{result.stdout}"
            else:
                return f"❌ Update fehlgeschlagen:\n{result.stderr}"
        except Exception as e:
            return f"❌ Fehler: {e}"

    def restart_app(self) -> None:
        """Restart the toolkit application."""
        import threading

        def delayed_restart():
            import time
            time.sleep(1)
            os.execv(sys.executable, [sys.executable, str(PROJECT_DIR / "app.py")] + sys.argv[1:])

        threading.Thread(target=delayed_restart, daemon=True).start()

    def render(self) -> gr.Blocks:
        """Render the System Info UI."""

        with gr.Blocks() as ui:
            gr.Markdown("## 💻 System Info")

            with gr.Row():
                refresh_btn = gr.Button("🔄 Aktualisieren", variant="primary", scale=2)
                upgrade_btn = gr.Button("⬆️ Upgrade & Restart", variant="secondary", scale=1)

            with gr.Row():
                with gr.Column():
                    gpu_info = gr.Markdown(self.get_gpu_info())
                with gr.Column():
                    mem_info = gr.Markdown(self.get_memory_info())

            with gr.Row():
                with gr.Column():
                    disk_info = gr.Markdown(self.get_disk_info())
                with gr.Column():
                    env_info = gr.Markdown(self.get_environment())

            with gr.Row():
                with gr.Column():
                    toolkit_info = gr.Markdown(self.get_toolkit_info())
                with gr.Column():
                    upgrade_output = gr.Textbox(
                        label="Upgrade Status",
                        lines=4,
                        interactive=False,
                        value="",
                    )

            def on_refresh():
                return (
                    self.get_gpu_info(),
                    self.get_memory_info(),
                    self.get_disk_info(),
                    self.get_environment(),
                    self.get_toolkit_info(),
                )

            def on_upgrade():
                result = self.upgrade_toolkit()
                if "erfolgreich" in result:
                    self.restart_app()
                    return result + "\n\n🔄 Neustart in 1 Sekunde..."
                return result

            refresh_btn.click(
                on_refresh,
                outputs=[gpu_info, mem_info, disk_info, env_info, toolkit_info],
            )

            upgrade_btn.click(
                on_upgrade,
                outputs=[upgrade_output],
            )

        return ui
