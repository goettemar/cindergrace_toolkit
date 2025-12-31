"""System Info Addon - Display GPU, memory and disk information."""

import os
import subprocess
from pathlib import Path

import gradio as gr

from core.base_addon import BaseAddon


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
            paths_to_check = [
                ("/workspace", "RunPod Workspace"),
                ("/runpod-volume", "RunPod Volume"),
                ("/content", "Colab Content"),
                (str(Path.home()), "Home"),
            ]

            output = "### Speicherplatz\n\n"

            for path, label in paths_to_check:
                if os.path.exists(path):
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

        if os.path.exists("/workspace") and os.path.exists("/runpod-volume"):
            output += "**Plattform:** 🚀 RunPod\n"
            # Check for pod info
            pod_id = os.environ.get("RUNPOD_POD_ID", "unbekannt")
            output += f"- Pod ID: `{pod_id}`\n"
        elif os.path.exists("/content") and "COLAB_GPU" in os.environ:
            output += "**Plattform:** 📓 Google Colab\n"
        else:
            output += "**Plattform:** 🖥️ Lokal\n"

        # Python version
        import sys
        output += f"- Python: {sys.version.split()[0]}\n"

        # CUDA
        cuda_version = os.environ.get("CUDA_VERSION", "unbekannt")
        output += f"- CUDA: {cuda_version}\n"

        return output

    def render(self) -> gr.Blocks:
        """Render the System Info UI."""

        with gr.Blocks() as ui:
            gr.Markdown("## 💻 System Info")

            refresh_btn = gr.Button("🔄 Aktualisieren", variant="primary")

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

            def on_refresh():
                return (
                    self.get_gpu_info(),
                    self.get_memory_info(),
                    self.get_disk_info(),
                    self.get_environment(),
                )

            refresh_btn.click(
                on_refresh,
                outputs=[gpu_info, mem_info, disk_info, env_info],
            )

        return ui
