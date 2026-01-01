#!/usr/bin/env python3
"""
Sync Custom Nodes - Install/update custom nodes from config.

Usage:
    python sync_nodes.py [--comfyui-path PATH] [--remove-disabled] [--dry-run]

This script reads data/custom_nodes.json and ensures all enabled nodes
are installed and up-to-date in the ComfyUI custom_nodes directory.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# Find project root (where data/ is located)
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
CONFIG_DIR = PROJECT_DIR / "config"


def load_custom_nodes_config() -> Dict:
    """Load custom_nodes.json from data directory."""
    config_file = DATA_DIR / "custom_nodes.json"
    if not config_file.exists():
        print(f"[ERROR] Config not found: {config_file}")
        sys.exit(1)

    with open(config_file, "r", encoding="utf-8") as f:
        return json.load(f)


def detect_comfyui_path() -> Optional[Path]:
    """Auto-detect ComfyUI path based on environment."""
    # Try common locations
    candidates = [
        Path("/workspace/ComfyUI"),  # RunPod
        Path("/content/ComfyUI"),    # Colab
        Path.home() / "ComfyUI",     # Local
        Path.home() / "projekte" / "ComfyUI",  # Local alt
    ]

    # Also check config files
    for config_path in [PROJECT_DIR / ".config" / "config.json", CONFIG_DIR / "config.json"]:
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)

                paths = config.get("paths", {}).get("comfyui", {})

                # Detect environment
                if os.path.exists("/workspace"):
                    env = "runpod"
                elif os.path.exists("/content"):
                    env = "colab"
                else:
                    env = "local"

                comfy_path = paths.get(env, "")
                if comfy_path:
                    if comfy_path.startswith("~"):
                        comfy_path = os.path.expanduser(comfy_path)
                    candidates.insert(0, Path(comfy_path))
            except (json.JSONDecodeError, KeyError):
                pass

    for candidate in candidates:
        if candidate.exists() and (candidate / "main.py").exists():
            return candidate

    return None


def get_node_folder_name(url: str, folder_override: str = None) -> str:
    """Extract folder name from git URL or use override."""
    if folder_override:
        return folder_override
    # https://github.com/user/ComfyUI-Something.git -> ComfyUI-Something
    name = url.rstrip("/").rstrip(".git").split("/")[-1]
    return name


def run_command(cmd: List[str], cwd: Optional[Path] = None, quiet: bool = False) -> Tuple[int, str]:
    """Run a shell command and return (returncode, output)."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=300
        )
        output = result.stdout + result.stderr
        if not quiet and result.returncode != 0:
            print(f"      Command failed: {' '.join(cmd)}")
            print(f"      Output: {output[:500]}")
        return result.returncode, output
    except subprocess.TimeoutExpired:
        return -1, "Command timed out"
    except Exception as e:
        return -1, str(e)


def install_requirements(node_path: Path, quiet: bool = False) -> bool:
    """Install requirements.txt if it exists."""
    req_file = node_path / "requirements.txt"
    if not req_file.exists():
        return True

    if not quiet:
        print(f"      Installing requirements...")

    code, _ = run_command(
        [sys.executable, "-m", "pip", "install", "-q", "-r", str(req_file)],
        cwd=node_path,
        quiet=quiet
    )
    return code == 0


def clone_node(url: str, target_dir: Path, quiet: bool = False) -> bool:
    """Clone a git repository."""
    if not quiet:
        print(f"      Cloning from {url}...")

    code, _ = run_command(
        ["git", "clone", "--quiet", url, str(target_dir)],
        quiet=quiet
    )

    if code == 0:
        install_requirements(target_dir, quiet)

    return code == 0


def update_node(node_path: Path, quiet: bool = False) -> Tuple[bool, bool]:
    """
    Update a node via git pull.
    Returns: (success, was_updated)
    """
    # Check for updates
    code, _ = run_command(["git", "fetch", "--quiet"], cwd=node_path, quiet=True)
    if code != 0:
        return False, False

    # Get local and remote commits
    code, local = run_command(["git", "rev-parse", "HEAD"], cwd=node_path, quiet=True)
    if code != 0:
        return False, False

    code, remote = run_command(["git", "rev-parse", "@{u}"], cwd=node_path, quiet=True)
    if code != 0:
        # No upstream, skip update
        return True, False

    if local.strip() == remote.strip():
        return True, False

    # Pull updates
    if not quiet:
        print(f"      Updating...")

    code, _ = run_command(["git", "pull", "--quiet"], cwd=node_path, quiet=quiet)
    if code == 0:
        install_requirements(node_path, quiet)
        return True, True

    return False, False


def remove_node(node_path: Path, quiet: bool = False) -> bool:
    """Remove a node directory."""
    import shutil

    if not quiet:
        print(f"      Removing {node_path.name}...")

    try:
        shutil.rmtree(node_path)
        return True
    except Exception as e:
        print(f"      Error removing: {e}")
        return False


def sync_nodes(
    comfyui_path: Path,
    remove_disabled: bool = False,
    dry_run: bool = False,
    quiet: bool = False
) -> Dict[str, int]:
    """
    Sync custom nodes based on config.

    Returns: {"installed": n, "updated": n, "removed": n, "skipped": n, "errors": n}
    """
    config = load_custom_nodes_config()
    nodes = config.get("nodes", [])

    custom_nodes_dir = comfyui_path / "custom_nodes"
    if not custom_nodes_dir.exists():
        print(f"[ERROR] Custom nodes directory not found: {custom_nodes_dir}")
        sys.exit(1)

    stats = {"installed": 0, "updated": 0, "removed": 0, "skipped": 0, "errors": 0}

    # Process enabled nodes
    for node in nodes:
        node_id = node.get("id", "")
        name = node.get("name", node_id)
        url = node.get("url", "")
        enabled = node.get("enabled", False)
        folder_override = node.get("folder", None)

        if not url:
            if not quiet:
                print(f"  [SKIP] {name}: No URL")
            stats["skipped"] += 1
            continue

        folder_name = get_node_folder_name(url, folder_override)
        node_path = custom_nodes_dir / folder_name
        exists = node_path.exists()

        if enabled:
            if exists:
                # Update existing node
                if not quiet:
                    print(f"  [CHECK] {name}")

                if dry_run:
                    if not quiet:
                        print(f"      Would check for updates")
                    stats["skipped"] += 1
                else:
                    success, was_updated = update_node(node_path, quiet)
                    if success:
                        if was_updated:
                            if not quiet:
                                print(f"      Updated!")
                            stats["updated"] += 1
                        else:
                            if not quiet:
                                print(f"      Already up-to-date")
                            stats["skipped"] += 1
                    else:
                        stats["errors"] += 1
            else:
                # Install new node
                if not quiet:
                    print(f"  [INSTALL] {name}")

                if dry_run:
                    if not quiet:
                        print(f"      Would clone from {url}")
                    stats["skipped"] += 1
                else:
                    if clone_node(url, node_path, quiet):
                        if not quiet:
                            print(f"      Installed!")
                        stats["installed"] += 1
                    else:
                        stats["errors"] += 1
        else:
            # Node is disabled
            if exists and remove_disabled:
                if not quiet:
                    print(f"  [REMOVE] {name}")

                if node.get("required", False):
                    if not quiet:
                        print(f"      Skipping (required node)")
                    stats["skipped"] += 1
                elif dry_run:
                    if not quiet:
                        print(f"      Would remove {folder_name}")
                    stats["skipped"] += 1
                else:
                    if remove_node(node_path, quiet):
                        stats["removed"] += 1
                    else:
                        stats["errors"] += 1
            elif exists:
                if not quiet:
                    print(f"  [DISABLED] {name} (still installed)")
                stats["skipped"] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(description="Sync ComfyUI custom nodes from config")
    parser.add_argument(
        "--comfyui-path",
        type=str,
        help="Path to ComfyUI installation"
    )
    parser.add_argument(
        "--remove-disabled",
        action="store_true",
        help="Remove nodes that are disabled in config"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Minimal output"
    )

    args = parser.parse_args()

    # Determine ComfyUI path
    if args.comfyui_path:
        comfyui_path = Path(args.comfyui_path)
    else:
        comfyui_path = detect_comfyui_path()

    if not comfyui_path or not comfyui_path.exists():
        print("[ERROR] ComfyUI path not found. Use --comfyui-path to specify.")
        sys.exit(1)

    if not args.quiet:
        print(f"ComfyUI: {comfyui_path}")
        print(f"Config: {DATA_DIR / 'custom_nodes.json'}")
        if args.dry_run:
            print("[DRY RUN]")
        print()

    stats = sync_nodes(
        comfyui_path,
        remove_disabled=args.remove_disabled,
        dry_run=args.dry_run,
        quiet=args.quiet
    )

    if not args.quiet:
        print()
        print(f"Done: {stats['installed']} installed, {stats['updated']} updated, "
              f"{stats['removed']} removed, {stats['skipped']} skipped, {stats['errors']} errors")

    sys.exit(0 if stats["errors"] == 0 else 1)


if __name__ == "__main__":
    main()
