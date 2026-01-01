#!/usr/bin/env python3
"""
Sync Custom Nodes - Install/update custom nodes using ComfyUI-Manager CLI.

Usage:
    python sync_nodes.py [--comfyui-path PATH] [--remove-disabled] [--dry-run]

This script reads data/custom_nodes.json and uses cm-cli.py to manage nodes.
ComfyUI-Manager is installed via git first, then cm-cli handles all other nodes.

Errors are logged to logs/sync_errors.log for the toolkit to display.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# Find project root (where data/ is located)
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
CONFIG_DIR = PROJECT_DIR / "config"
LOGS_DIR = PROJECT_DIR / "logs"

# Ensure logs directory exists
LOGS_DIR.mkdir(exist_ok=True)
ERROR_LOG = LOGS_DIR / "sync_errors.log"


def log_error(node_name: str, operation: str, error_msg: str) -> None:
    """Log error to sync_errors.log with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] [{operation}] {node_name}: {error_msg}\n"

    try:
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception:
        pass


def clear_error_log() -> None:
    """Clear the error log at the start of a sync."""
    try:
        if ERROR_LOG.exists():
            ERROR_LOG.unlink()
    except Exception:
        pass


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
    candidates = [
        Path("/workspace/ComfyUI"),  # RunPod
        Path("/content/ComfyUI"),    # Colab
        Path.home() / "ComfyUI",     # Local
        Path.home() / "projekte" / "ComfyUI",  # Local alt
    ]

    for config_path in [PROJECT_DIR / ".config" / "config.json", CONFIG_DIR / "config.json"]:
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)

                paths = config.get("paths", {}).get("comfyui", {})

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


def run_command(
    cmd: List[str],
    cwd: Optional[Path] = None,
    quiet: bool = False,
    timeout: int = 300
) -> Tuple[int, str]:
    """Run a shell command and return (returncode, output)."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        output = result.stdout + result.stderr
        if not quiet and result.returncode != 0:
            print(f"      Command failed: {' '.join(cmd[:3])}...")
        return result.returncode, output
    except subprocess.TimeoutExpired:
        return -1, f"Command timed out after {timeout}s"
    except Exception as e:
        return -1, str(e)


def ensure_manager_installed(custom_nodes_dir: Path, manager_config: Dict, quiet: bool = False) -> bool:
    """Ensure ComfyUI-Manager is installed (required for cm-cli)."""
    manager_path = custom_nodes_dir / "ComfyUI-Manager"

    if manager_path.exists():
        if not quiet:
            print("  [OK] ComfyUI-Manager already installed")
        return True

    url = manager_config.get("url", "https://github.com/ltdrdata/ComfyUI-Manager.git")

    if not quiet:
        print("  [INSTALL] ComfyUI-Manager (required for cm-cli)")
        print(f"      Cloning from {url}...")

    code, output = run_command(
        ["git", "clone", "--quiet", "--depth", "1", url, str(manager_path)],
        timeout=180
    )

    if code != 0:
        log_error("ComfyUI-Manager", "CLONE", output[:200])
        print(f"      [ERROR] Clone failed: {output[:100]}")
        return False

    # Install requirements
    req_file = manager_path / "requirements.txt"
    if req_file.exists():
        if not quiet:
            print("      Installing requirements...")
        run_command(
            [sys.executable, "-m", "pip", "install", "-q", "-r", str(req_file)],
            cwd=manager_path,
            quiet=True
        )

    if not quiet:
        print("      Installed!")
    return True


def run_cm_cli(
    comfyui_path: Path,
    action: str,
    nodes: List[str],
    quiet: bool = False
) -> Tuple[bool, str]:
    """Run cm-cli.py with given action and nodes."""
    cm_cli = comfyui_path / "custom_nodes" / "ComfyUI-Manager" / "cm-cli.py"

    if not cm_cli.exists():
        return False, f"cm-cli.py not found at {cm_cli}"

    cmd = [sys.executable, str(cm_cli), action] + nodes

    if not quiet:
        print(f"      Running: cm-cli.py {action} {' '.join(nodes[:3])}{'...' if len(nodes) > 3 else ''}")

    code, output = run_command(cmd, cwd=comfyui_path, timeout=600)

    return code == 0, output


def sync_nodes(
    comfyui_path: Path,
    remove_disabled: bool = False,
    dry_run: bool = False,
    quiet: bool = False
) -> Dict[str, int]:
    """
    Sync custom nodes using cm-cli.

    Returns: {"installed": n, "updated": n, "removed": n, "skipped": n, "errors": n}
    """
    if not dry_run:
        clear_error_log()

    config = load_custom_nodes_config()
    custom_nodes_dir = comfyui_path / "custom_nodes"

    if not custom_nodes_dir.exists():
        print(f"[ERROR] Custom nodes directory not found: {custom_nodes_dir}")
        sys.exit(1)

    stats = {"installed": 0, "updated": 0, "removed": 0, "skipped": 0, "errors": 0}

    # Step 1: Ensure ComfyUI-Manager is installed
    manager_config = config.get("manager", {})
    if not ensure_manager_installed(custom_nodes_dir, manager_config, quiet):
        print("[ERROR] Failed to install ComfyUI-Manager. Cannot proceed.")
        stats["errors"] += 1
        return stats

    # Step 2: Get enabled and disabled nodes
    nodes = config.get("nodes", [])
    enabled_nodes = [n["name"] for n in nodes if n.get("enabled", False) and n.get("name")]
    disabled_nodes = [n["name"] for n in nodes if not n.get("enabled", False) and n.get("name")]

    # Step 3: Install/Update enabled nodes
    if enabled_nodes:
        if not quiet:
            print(f"\n  [SYNC] {len(enabled_nodes)} enabled node(s)")

        if dry_run:
            for name in enabled_nodes:
                print(f"      Would install/update: {name}")
            stats["skipped"] += len(enabled_nodes)
        else:
            # cm-cli install handles both install and update
            success, output = run_cm_cli(comfyui_path, "install", enabled_nodes, quiet)

            if success:
                # Parse output to count what happened
                for name in enabled_nodes:
                    if f"installed" in output.lower() or f"already" in output.lower():
                        stats["installed"] += 1
                    else:
                        stats["skipped"] += 1
                if not quiet:
                    print("      Done!")
            else:
                log_error("cm-cli install", "INSTALL", output[:200])
                if not quiet:
                    print(f"      [WARNING] Some nodes may have failed")
                    print(f"      {output[:300]}")
                stats["errors"] += len(enabled_nodes)

    # Step 4: Remove disabled nodes (if requested)
    if remove_disabled and disabled_nodes:
        if not quiet:
            print(f"\n  [REMOVE] {len(disabled_nodes)} disabled node(s)")

        if dry_run:
            for name in disabled_nodes:
                print(f"      Would uninstall: {name}")
            stats["skipped"] += len(disabled_nodes)
        else:
            success, output = run_cm_cli(comfyui_path, "uninstall", disabled_nodes, quiet)

            if success:
                stats["removed"] += len(disabled_nodes)
                if not quiet:
                    print("      Done!")
            else:
                log_error("cm-cli uninstall", "UNINSTALL", output[:200])
                if not quiet:
                    print(f"      [WARNING] Some nodes may have failed to uninstall")
                stats["errors"] += len(disabled_nodes)

    return stats


def update_all_nodes(comfyui_path: Path, quiet: bool = False) -> bool:
    """Update all installed nodes using cm-cli."""
    if not quiet:
        print("  [UPDATE] Updating all installed nodes...")

    success, output = run_cm_cli(comfyui_path, "update", ["all"], quiet)

    if not quiet:
        if success:
            print("      Done!")
        else:
            print(f"      [ERROR] Update failed: {output[:200]}")

    return success


def main():
    parser = argparse.ArgumentParser(description="Sync ComfyUI custom nodes using cm-cli")
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
        "--update-all",
        action="store_true",
        help="Update all installed nodes"
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

    if args.update_all:
        success = update_all_nodes(comfyui_path, args.quiet)
        sys.exit(0 if success else 1)

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
