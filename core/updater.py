"""Git-based Auto-Updater for Cindergrace Toolkit."""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class UpdateInfo:
    """Information about available update."""

    current_commit: str
    remote_commit: str
    has_update: bool
    commits_behind: int
    change_summary: str


class GitUpdater:
    """Handle automatic updates via git.

    Workflow:
    1. Check if we're in a git repo
    2. Fetch remote changes
    3. Compare local vs remote
    4. Pull if update available
    """

    def __init__(self, repo_path: Path | None = None):
        self.repo_path = repo_path or Path(__file__).parent.parent
        self._config = self._load_config()

    def _load_config(self) -> dict:
        """Load update config from config.json."""
        config_file = self.repo_path / "config" / "config.json"
        if config_file.exists():
            with open(config_file, encoding="utf-8") as f:
                return json.load(f).get("update", {})
        return {}

    def _run_git(self, *args, capture: bool = True) -> tuple[bool, str]:
        """Run a git command in the repo directory."""
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.repo_path,
                capture_output=capture,
                text=True,
                timeout=30,
            )
            return result.returncode == 0, result.stdout.strip()
        except subprocess.TimeoutExpired:
            return False, "Timeout"
        except FileNotFoundError:
            return False, "Git nicht installiert"
        except Exception as e:
            return False, str(e)

    def is_git_repo(self) -> bool:
        """Check if we're in a git repository."""
        git_dir = self.repo_path / ".git"
        return git_dir.exists()

    def get_current_commit(self) -> str | None:
        """Get current commit hash."""
        success, output = self._run_git("rev-parse", "HEAD")
        return output[:8] if success else None

    def get_current_branch(self) -> str | None:
        """Get current branch name."""
        success, output = self._run_git("rev-parse", "--abbrev-ref", "HEAD")
        return output if success else None

    def fetch_remote(self) -> bool:
        """Fetch changes from remote."""
        branch = self._config.get("branch", "main")
        success, _ = self._run_git("fetch", "origin", branch)
        return success

    def check_for_updates(self) -> UpdateInfo | None:
        """Check if updates are available."""
        if not self.is_git_repo():
            print("[Updater] Kein Git Repository")
            return None

        # Fetch latest
        if not self.fetch_remote():
            print("[Updater] Fetch fehlgeschlagen")
            return None

        branch = self._config.get("branch", "main")

        # Get current commit
        current = self.get_current_commit()
        if not current:
            return None

        # Get remote commit
        success, remote = self._run_git("rev-parse", f"origin/{branch}")
        if not success:
            return None
        remote = remote[:8]

        # Count commits behind
        success, count_str = self._run_git("rev-list", "--count", f"HEAD..origin/{branch}")
        commits_behind = int(count_str) if success and count_str.isdigit() else 0

        # Get change summary if updates available
        change_summary = ""
        if commits_behind > 0:
            success, log = self._run_git("log", "--oneline", f"HEAD..origin/{branch}", "--", "-10")
            if success:
                change_summary = log

        return UpdateInfo(
            current_commit=current,
            remote_commit=remote,
            has_update=commits_behind > 0,
            commits_behind=commits_behind,
            change_summary=change_summary,
        )

    def pull_updates(self) -> tuple[bool, str]:
        """Pull latest changes from remote."""
        if not self.is_git_repo():
            return False, "Kein Git Repository"

        branch = self._config.get("branch", "main")

        # Check for local changes
        success, status = self._run_git("status", "--porcelain")
        if success and status:
            # Stash local changes
            self._run_git("stash", "push", "-m", "auto-stash before update")

        # Pull
        success, output = self._run_git("pull", "origin", branch)

        if success:
            return True, f"Update erfolgreich: {output}"
        else:
            return False, f"Update fehlgeschlagen: {output}"

    def auto_update_if_enabled(self) -> tuple[bool, str]:
        """Check and apply updates if auto-update is enabled."""
        if not self._config.get("enabled", True):
            return False, "Updates deaktiviert"

        if not self._config.get("auto_update", True):
            return False, "Auto-Update deaktiviert"

        print("[Updater] Prüfe auf Updates...")

        info = self.check_for_updates()
        if not info:
            return False, "Update-Check fehlgeschlagen"

        if not info.has_update:
            print(f"[Updater] Bereits aktuell ({info.current_commit})")
            return False, "Bereits aktuell"

        print(f"[Updater] {info.commits_behind} neue Commits verfügbar")
        if info.change_summary:
            print(f"[Updater] Änderungen:\n{info.change_summary}")

        success, message = self.pull_updates()
        if success:
            print(f"[Updater] ✅ {message}")
        else:
            print(f"[Updater] ❌ {message}")

        return success, message


def check_and_update() -> bool:
    """Convenience function to check and apply updates."""
    updater = GitUpdater()
    success, _ = updater.auto_update_if_enabled()
    return success
