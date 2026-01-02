#!/usr/bin/env python3
"""Cindergrace Toolkit - Modular ComfyUI companion tools.

Usage:
    python app.py                    # Auto-detect release based on environment
    python app.py --release full     # Load specific release
    python app.py --release runpod   # RunPod optimized release
    python app.py --port 7861        # Custom port

Environment Variables:
    TOOLKIT_RELEASE: Override release selection
    TOOLKIT_PROFILE_URL: Remote profile base URL
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import gradio as gr

from core.addon_loader import AddonLoader
from core.config_manager import ConfigManager
from core.profile_sync import ProfileSyncService

# === Settings Store ===

SETTINGS_DIR = Path(__file__).parent / ".config"
SETTINGS_FILE = SETTINGS_DIR / "app_settings.json"


def _load_app_settings() -> dict:
    """Load app settings from file."""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_app_settings(settings: dict) -> None:
    """Save app settings to file."""
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


def is_disclaimer_accepted() -> bool:
    """Check if user has accepted the disclaimer."""
    settings = _load_app_settings()
    return settings.get("disclaimer_accepted", False)


def accept_disclaimer() -> str:
    """Mark disclaimer as accepted and return acceptance date."""
    settings = _load_app_settings()
    acceptance_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    settings["disclaimer_accepted"] = True
    settings["disclaimer_accepted_date"] = acceptance_date
    _save_app_settings(settings)
    return acceptance_date


def get_disclaimer_date() -> str:
    """Get disclaimer acceptance date."""
    settings = _load_app_settings()
    return settings.get("disclaimer_accepted_date", "Unknown")


# === Disclaimer Text ===

DISCLAIMER_TEXT = """
---

### 1. Disclaimer of Warranty

This software is provided **"AS IS"** without warranty of any kind, express or implied, including but not limited to:

- No warranty of merchantability or fitness for a particular purpose
- No warranty of error-free or uninterrupted operation
- No warranty regarding the accuracy or completeness of results

**Use at your own risk.**

---

### 2. Limitation of Liability

The developers and rights holders are not liable for:

- Direct, indirect, incidental, or consequential damages
- Data loss or corruption
- Business interruption
- Any other damages arising from the use of this software

---

### 3. Copyright & Generated Content

- You are solely responsible for the content you create with this software
- You must ensure that generated content does not infringe third-party rights
- The developers assume no responsibility for copyright infringement

---

### 4. Third-Party Models

This software uses AI models from third parties (e.g., WAN 2.2, Flux, LTX-Video, SDXL).
You are required to comply with the **respective license terms of these models**.
The developers assume no responsibility for license violations by users.

---

### 5. Alpha/Beta Status

This software is in **Alpha/Beta stage**. You accept that:

- Errors, crashes, and data loss may occur
- Changes may be made without notice
- Development may be discontinued without notice
- There is no entitlement to support or updates

---

### 6. Indemnification

You agree to indemnify and hold harmless the developers and rights holders from any claims,
damages, losses, or expenses (including legal fees) arising from:

- Your use of the software
- Content you create with the software
- Your violation of these terms
- Your violation of any third-party rights

---

**By using this software, you confirm that you have read, understood, and accepted these terms.**
"""


# === Disk Info ===


def _get_disk_info(config: ConfigManager) -> str:
    """Get disk space info for relevant paths."""
    import shutil

    lines = []

    def format_size(bytes_val: int) -> str:
        gb = bytes_val / (1024**3)
        if gb >= 1:
            return f"{gb:.1f} GB"
        mb = bytes_val / (1024**2)
        return f"{mb:.0f} MB"

    def get_disk_status(path: str, name: str) -> str:
        if not path or not os.path.exists(path):
            return f"- {name}: Not found"

        try:
            usage = shutil.disk_usage(path)
            free = format_size(usage.free)
            total = format_size(usage.total)
            percent_used = (usage.used / usage.total) * 100

            # Warning if less than 10GB free or >90% used
            if usage.free < 10 * 1024**3 or percent_used > 90:
                icon = "Warning"
            else:
                icon = "OK"

            return f"- {name}: {icon} - {free} free / {total} ({percent_used:.0f}% used)"
        except Exception as e:
            return f"- {name}: Error: {e}"

    # ComfyUI models path (most important)
    models_path = config.get_models_path()
    if models_path:
        lines.append(get_disk_status(models_path, f"Models ({models_path})"))
    else:
        lines.append("- Models: Not configured")

    # Environment-specific paths
    if config.is_runpod():
        lines.append(get_disk_status("/workspace", "Workspace"))
        lines.append(get_disk_status("/runpod-volume", "Volume"))
    elif config.is_colab():
        lines.append(get_disk_status("/content", "Content"))

    return "\n            ".join(lines) if lines else "No paths configured"


def detect_release(config: ConfigManager) -> str:
    """Auto-detect which release to load based on environment."""
    # Check environment variable first
    env_release = os.environ.get("TOOLKIT_RELEASE", "").lower()
    if env_release:
        return env_release

    # Auto-detect environment
    if config.is_runpod():
        return "runpod"
    if config.is_colab():
        return "runpod"  # Colab uses same profile as RunPod

    return "full"


def create_app(release: str, profile_url: str = "") -> gr.Blocks:
    """Create the Gradio app with loaded addons."""

    config = ConfigManager()
    loader = AddonLoader()
    profile_sync = ProfileSyncService(profile_url)

    # Load release configuration
    actual_release = release
    try:
        release_config = loader.load_release_config(release)
        print(f"[Toolkit] Loaded release: {release_config.get('name', release)}")
    except FileNotFoundError:
        print(f"[Toolkit] Warning: Release '{release}' not found, using 'minimal'")
        actual_release = "minimal"
        release_config = loader.load_release_config(actual_release)

    # Load addons (use actual_release to match config)
    addons = loader.load_release(actual_release)
    print(f"[Toolkit] Loaded {len(addons)} addons")

    # Setup remote profiles if configured
    remote_config = release_config.get("remote_profiles", {})
    if remote_config.get("enabled") and remote_config.get("url"):
        profile_sync.set_base_url(remote_config["url"])
        if remote_config.get("auto_sync"):
            profile_sync.fetch_index()

    # Check disclaimer status
    disclaimer_accepted = is_disclaimer_accepted()

    # Build Gradio UI
    with gr.Blocks(title="Cindergrace Toolkit") as app:
        # === DISCLAIMER VIEW (shown if not accepted) ===
        with gr.Column(visible=not disclaimer_accepted) as disclaimer_view:
            gr.Markdown(
                """
                # Cindergrace Toolkit

                ## Terms of Use & Disclaimer

                Please read and accept the following terms before continuing:
                """
            )

            gr.Markdown(DISCLAIMER_TEXT)

            accept_checkbox = gr.Checkbox(
                label="I have read, understood, and accept the Terms of Use and Disclaimer",
                value=False,
            )

            accept_btn = gr.Button("Accept & Continue", variant="primary", interactive=False)

            accept_status = gr.Textbox(visible=False)

        # === MAIN APP VIEW (shown after acceptance) ===
        with gr.Column(visible=disclaimer_accepted) as main_view:
            # Header
            gr.Markdown(
                f"""
                # Cindergrace Toolkit
                **Release:** {release_config.get("name", release)} v{release_config.get("version", "1.0.0")}
                """
            )

            # Addon Tabs
            if addons:
                with gr.Tabs():
                    for addon in addons:
                        with gr.Tab(addon.get_tab_name()):
                            addon.render()
            else:
                gr.Markdown("*No addons loaded. Please check release configuration.*")

            # Footer with config info and disk status
            with gr.Accordion("Configuration & Storage", open=True):
                # Get disk info
                disk_info = _get_disk_info(config)

                comfy_path = config.get_comfyui_path()
                disclaimer_date = get_disclaimer_date() if disclaimer_accepted else "Not accepted"

                gr.Markdown(f"""
                **System:**
                - **Environment:** {config.get_environment()}
                - **ComfyUI:** {comfy_path or "Not found"}
                - **Remote Profiles:** {"Enabled" if remote_config.get("enabled") else "Disabled"}
                - **Terms Accepted:** {disclaimer_date}

                **Storage:**
                {disk_info}
                """)

        # === Event Handlers ===

        def on_checkbox_change(checked):
            return gr.update(interactive=checked)

        def on_accept_click():
            acceptance_date = accept_disclaimer()
            # Return updates to hide disclaimer and show main view
            return (
                gr.update(visible=False),  # Hide disclaimer
                gr.update(visible=True),  # Show main view
                f"Accepted on {acceptance_date}",
            )

        accept_checkbox.change(
            fn=on_checkbox_change,
            inputs=[accept_checkbox],
            outputs=[accept_btn],
        )

        accept_btn.click(
            fn=on_accept_click,
            outputs=[disclaimer_view, main_view, accept_status],
        )

    return app


def main():
    parser = argparse.ArgumentParser(description="Cindergrace Toolkit")
    parser.add_argument(
        "--release",
        "-r",
        default="",
        help="Release configuration to load (full, runpod, minimal)",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=7861,
        help="Port to run on (default: 7861)",
    )
    parser.add_argument(
        "--profile-url",
        default="",
        help="Base URL for remote profiles",
    )
    parser.add_argument(
        "--share",
        action="store_true",
        help="Create a public Gradio link",
    )

    args = parser.parse_args()

    # Initialize config
    config = ConfigManager()

    # Determine release
    release = args.release or detect_release(config)

    # Profile URL from args or environment
    profile_url = args.profile_url or os.environ.get("TOOLKIT_PROFILE_URL", "")

    print(f"[Toolkit] Starting with release: {release}")
    print(f"[Toolkit] Environment: {config.get_environment()}")

    # Create and launch app
    app = create_app(release, profile_url)

    # Launch configuration
    launch_kwargs = {
        "server_port": args.port,
        "share": args.share,
        "theme": gr.themes.Soft(),
    }

    # RunPod/Colab specific settings
    if config.is_runpod():
        launch_kwargs["server_name"] = "0.0.0.0"
        launch_kwargs["share"] = False  # RunPod has its own proxy
        print("[Toolkit] RunPod mode: server_name=0.0.0.0, share=False")
    elif config.is_colab():
        launch_kwargs["server_name"] = "0.0.0.0"
        launch_kwargs["share"] = True  # Colab needs share for public access
        print("[Toolkit] Colab mode: server_name=0.0.0.0, share=True")

    # Try to find an available port
    import socket

    def find_free_port(start_port: int, max_attempts: int = 10) -> int:
        for port in range(start_port, start_port + max_attempts):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(("", port))
                    return port
            except OSError:
                continue
        return start_port + max_attempts

    port = find_free_port(args.port)
    if port != args.port:
        print(f"[Toolkit] Port {args.port} in use, using port {port}")
    launch_kwargs["server_port"] = port

    app.launch(**launch_kwargs)


if __name__ == "__main__":
    main()
