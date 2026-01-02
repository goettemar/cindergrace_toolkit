#!/usr/bin/env python3
"""
Sync Workflows - Copy workflows from toolkit to ComfyUI.

Usage:
    python sync_workflows.py [--comfyui-path PATH] [--dry-run]

This script copies all .json workflow files from data/workflows/ to
ComfyUI's user/default/workflows directory.
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

# Find project root (where data/ is located)
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
CONFIG_DIR = PROJECT_DIR / "config"
WORKFLOWS_DIR = DATA_DIR / "workflows"


def detect_comfyui_path() -> Path | None:
    """Auto-detect ComfyUI path based on environment."""
    candidates = [
        Path("/workspace/ComfyUI"),  # RunPod
        Path("/content/ComfyUI"),  # Colab
        Path.home() / "ComfyUI",  # Local
        Path.home() / "projekte" / "ComfyUI",  # Local alt
    ]

    # Also check config files
    for config_path in [PROJECT_DIR / ".config" / "config.json", CONFIG_DIR / "config.json"]:
        if config_path.exists():
            try:
                with open(config_path, encoding="utf-8") as f:
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


def get_workflows_target(comfyui_path: Path) -> Path:
    """Get the target directory for workflows in ComfyUI."""
    return comfyui_path / "user" / "default" / "workflows"


def get_source_workflows() -> list[Path]:
    """Get all workflow JSON files from data/workflows/."""
    if not WORKFLOWS_DIR.exists():
        return []

    workflows = []
    for f in WORKFLOWS_DIR.iterdir():
        if f.is_file() and f.suffix.lower() == ".json" and not f.name.startswith("."):
            workflows.append(f)

    return sorted(workflows)


def file_needs_update(source: Path, target: Path) -> bool:
    """Check if target file needs to be updated from source."""
    if not target.exists():
        return True

    # Compare modification times
    source_mtime = source.stat().st_mtime
    target_mtime = target.stat().st_mtime

    if source_mtime > target_mtime:
        return True

    # Compare sizes as quick content check
    if source.stat().st_size != target.stat().st_size:
        return True

    return False


def sync_workflows(
    comfyui_path: Path, dry_run: bool = False, quiet: bool = False
) -> dict[str, int]:
    """
    Sync workflows from toolkit to ComfyUI.

    Returns: {"copied": n, "updated": n, "skipped": n, "errors": n}
    """
    target_dir = get_workflows_target(comfyui_path)
    source_workflows = get_source_workflows()

    stats = {"copied": 0, "updated": 0, "skipped": 0, "errors": 0}

    if not source_workflows:
        if not quiet:
            print("  No workflows found in data/workflows/")
        return stats

    # Create target directory if needed
    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)

    for source_file in source_workflows:
        target_file = target_dir / source_file.name
        exists = target_file.exists()
        needs_update = file_needs_update(source_file, target_file)

        if needs_update:
            action = "UPDATE" if exists else "COPY"
            if not quiet:
                print(f"  [{action}] {source_file.name}")

            if dry_run:
                if not quiet:
                    print(f"      Would copy to {target_file}")
                stats["skipped"] += 1
            else:
                try:
                    shutil.copy2(source_file, target_file)
                    if exists:
                        stats["updated"] += 1
                    else:
                        stats["copied"] += 1
                except Exception as e:
                    if not quiet:
                        print(f"      Error: {e}")
                    stats["errors"] += 1
        else:
            if not quiet:
                print(f"  [OK] {source_file.name}")
            stats["skipped"] += 1

    return stats


def list_workflows(comfyui_path: Path, quiet: bool = False) -> None:
    """List all workflows in both source and target."""
    source_workflows = get_source_workflows()
    target_dir = get_workflows_target(comfyui_path)

    print("Source (data/workflows/):")
    if source_workflows:
        for wf in source_workflows:
            size_kb = wf.stat().st_size // 1024
            print(f"  {wf.name} ({size_kb} KB)")
    else:
        print("  (empty)")

    print()
    print(f"Target ({target_dir}):")
    if target_dir.exists():
        target_files = sorted(target_dir.glob("*.json"))
        if target_files:
            for wf in target_files:
                size_kb = wf.stat().st_size // 1024
                print(f"  {wf.name} ({size_kb} KB)")
        else:
            print("  (empty)")
    else:
        print("  (not created)")


def main():
    parser = argparse.ArgumentParser(description="Sync workflows from toolkit to ComfyUI")
    parser.add_argument("--comfyui-path", type=str, help="Path to ComfyUI installation")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be done without making changes"
    )
    parser.add_argument("--list", action="store_true", help="List workflows in source and target")
    parser.add_argument("--quiet", "-q", action="store_true", help="Minimal output")

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
        print(f"Source: {WORKFLOWS_DIR}")
        print(f"Target: {get_workflows_target(comfyui_path)}")
        if args.dry_run:
            print("[DRY RUN]")
        print()

    if args.list:
        list_workflows(comfyui_path, args.quiet)
        return

    stats = sync_workflows(comfyui_path, dry_run=args.dry_run, quiet=args.quiet)

    if not args.quiet:
        print()
        print(
            f"Done: {stats['copied']} copied, {stats['updated']} updated, "
            f"{stats['skipped']} skipped, {stats['errors']} errors"
        )

    sys.exit(0 if stats["errors"] == 0 else 1)


if __name__ == "__main__":
    main()
