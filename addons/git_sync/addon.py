"""Git Sync Addon - Push workflow changes to GitHub with encrypted token."""

import base64
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Optional, Tuple

import gradio as gr

from core.base_addon import BaseAddon


def _derive_key(password: str, salt: bytes = b"cindergrace") -> bytes:
    """Derive a key from password using PBKDF2."""
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000, dklen=32)


def _encrypt(data: str, password: str) -> str:
    """Simple XOR encryption with password-derived key."""
    key = _derive_key(password)
    data_bytes = data.encode()
    encrypted = bytes(a ^ b for a, b in zip(data_bytes, key * (len(data_bytes) // len(key) + 1)))
    return base64.b64encode(encrypted).decode()


def _decrypt(encrypted_data: str, password: str) -> Optional[str]:
    """Decrypt data with password."""
    try:
        key = _derive_key(password)
        encrypted_bytes = base64.b64decode(encrypted_data)
        decrypted = bytes(a ^ b for a, b in zip(encrypted_bytes, key * (len(encrypted_bytes) // len(key) + 1)))
        return decrypted.decode()
    except Exception:
        return None


class GitSyncAddon(BaseAddon):
    """Git Sync - Push workflow changes to GitHub."""

    PROJECT_DIR = Path(__file__).parent.parent.parent
    CONFIG_DIR = PROJECT_DIR / ".config"
    DATA_DIR = PROJECT_DIR / "data"
    CREDENTIALS_FILE = CONFIG_DIR / "git_credentials.enc"

    def __init__(self):
        super().__init__()
        self.name = "Git Sync"
        self.version = "1.0.0"
        self.icon = "🔄"

    def get_tab_name(self) -> str:
        return f"{self.icon} {self.name}"

    def on_load(self) -> None:
        self.CONFIG_DIR.mkdir(exist_ok=True)

    def _has_token(self) -> bool:
        """Check if encrypted token exists."""
        return self.CREDENTIALS_FILE.exists()

    def _save_token(self, token: str, password: str) -> str:
        """Save encrypted token."""
        try:
            encrypted = _encrypt(token, password)
            data = {"token": encrypted, "hint": "GitHub Personal Access Token"}
            with open(self.CREDENTIALS_FILE, "w") as f:
                json.dump(data, f)
            return "✅ Token gespeichert (verschlüsselt)"
        except Exception as e:
            return f"❌ Fehler: {e}"

    def _get_token(self, password: str) -> Optional[str]:
        """Get decrypted token."""
        if not self.CREDENTIALS_FILE.exists():
            return None
        try:
            with open(self.CREDENTIALS_FILE, "r") as f:
                data = json.load(f)
            return _decrypt(data.get("token", ""), password)
        except Exception:
            return None

    def _delete_token(self) -> str:
        """Delete stored token."""
        if self.CREDENTIALS_FILE.exists():
            self.CREDENTIALS_FILE.unlink()
            return "✅ Token gelöscht"
        return "Kein Token vorhanden"

    def _get_git_status(self) -> str:
        """Get git status for data directory."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain", "data/"],
                cwd=self.PROJECT_DIR,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                changes = result.stdout.strip()
                if changes:
                    return f"Änderungen:\n{changes}"
                return "Keine Änderungen"
            return f"Fehler: {result.stderr}"
        except Exception as e:
            return f"Fehler: {e}"

    def _git_push(self, password: str, commit_msg: str) -> str:
        """Commit and push changes to GitHub."""
        token = self._get_token(password)
        if not token:
            return "❌ Falsches Passwort oder kein Token"

        try:
            # Get remote URL
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=self.PROJECT_DIR,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return f"❌ Remote nicht gefunden: {result.stderr}"

            original_url = result.stdout.strip()

            # Convert SSH to HTTPS with token if needed
            if original_url.startswith("git@github.com:"):
                # SSH format: git@github.com:user/repo.git
                repo_path = original_url.replace("git@github.com:", "").rstrip(".git")
                auth_url = f"https://{token}@github.com/{repo_path}.git"
            elif original_url.startswith("https://github.com/"):
                # HTTPS format
                repo_path = original_url.replace("https://github.com/", "").rstrip(".git")
                auth_url = f"https://{token}@github.com/{repo_path}.git"
            else:
                return f"❌ Unbekanntes URL-Format: {original_url}"

            # Stage changes
            result = subprocess.run(
                ["git", "add", "data/"],
                cwd=self.PROJECT_DIR,
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Check if there are changes to commit
            result = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=self.PROJECT_DIR,
                timeout=10,
            )
            if result.returncode == 0:
                return "ℹ️ Keine Änderungen zum Committen"

            # Commit
            result = subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=self.PROJECT_DIR,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return f"❌ Commit fehlgeschlagen: {result.stderr}"

            # Push with auth URL (temporarily)
            result = subprocess.run(
                ["git", "push", auth_url, "HEAD:main"],
                cwd=self.PROJECT_DIR,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode == 0:
                return f"✅ Push erfolgreich!\n{commit_msg}"
            else:
                # Don't expose token in error
                error = result.stderr.replace(token, "***TOKEN***")
                return f"❌ Push fehlgeschlagen: {error}"

        except subprocess.TimeoutExpired:
            return "❌ Timeout"
        except Exception as e:
            return f"❌ Fehler: {e}"

    def render(self) -> gr.Blocks:
        """Render the Git Sync UI."""

        with gr.Blocks() as ui:
            gr.Markdown("## 🔄 Git Sync")
            gr.Markdown("*Push Workflow-Änderungen zu GitHub*")

            # === Token Status ===
            token_status = "✅ Token vorhanden" if self._has_token() else "❌ Kein Token"
            status_display = gr.Markdown(f"**Token Status:** {token_status}")

            # === Token Setup ===
            with gr.Accordion("Token einrichten", open=not self._has_token()):
                gr.Markdown("""
                **GitHub Personal Access Token erstellen:**
                1. GitHub → Settings → Developer Settings → Personal Access Tokens → Fine-grained tokens
                2. Generate new token mit `Contents: Read and write` Berechtigung
                3. Token hier einfügen und mit Passwort sichern
                """)

                token_input = gr.Textbox(
                    label="GitHub Token",
                    placeholder="ghp_xxxxxxxxxxxx",
                    type="password",
                )
                new_password = gr.Textbox(
                    label="Passwort (zum Verschlüsseln)",
                    placeholder="Sicheres Passwort wählen",
                    type="password",
                )
                with gr.Row():
                    save_token_btn = gr.Button("💾 Token speichern", variant="primary")
                    delete_token_btn = gr.Button("🗑️ Token löschen", variant="stop")

                token_result = gr.Textbox(label="Ergebnis", lines=1, interactive=False)

            gr.Markdown("---")

            # === Git Status ===
            gr.Markdown("### Änderungen")
            git_status = gr.Textbox(
                label="Git Status (data/)",
                value=self._get_git_status(),
                lines=5,
                interactive=False,
            )
            refresh_status_btn = gr.Button("🔄 Status aktualisieren")

            gr.Markdown("---")

            # === Push ===
            gr.Markdown("### Push zu GitHub")
            push_password = gr.Textbox(
                label="Passwort",
                placeholder="Passwort für Token-Entschlüsselung",
                type="password",
            )
            commit_message = gr.Textbox(
                label="Commit Message",
                value="Update workflow configs from RunPod",
                lines=1,
            )
            push_btn = gr.Button("🚀 Commit & Push", variant="primary")
            push_result = gr.Textbox(label="Ergebnis", lines=3, interactive=False)

            # === Event Handlers ===

            def on_save_token(token, password):
                if not token or not password:
                    return "Token und Passwort erforderlich", f"**Token Status:** ❌ Kein Token"
                if len(password) < 4:
                    return "Passwort muss mindestens 4 Zeichen haben", f"**Token Status:** ❌ Kein Token"
                result = self._save_token(token, password)
                has_token = self._has_token()
                status = "✅ Token vorhanden" if has_token else "❌ Kein Token"
                return result, f"**Token Status:** {status}"

            def on_delete_token():
                result = self._delete_token()
                return result, f"**Token Status:** ❌ Kein Token"

            def on_refresh_status():
                return self._get_git_status()

            def on_push(password, message):
                if not password:
                    return "Passwort erforderlich"
                if not message:
                    message = "Update from toolkit"
                return self._git_push(password, message)

            # === Wire Events ===
            save_token_btn.click(
                on_save_token,
                inputs=[token_input, new_password],
                outputs=[token_result, status_display],
            )

            delete_token_btn.click(
                on_delete_token,
                outputs=[token_result, status_display],
            )

            refresh_status_btn.click(
                on_refresh_status,
                outputs=[git_status],
            )

            push_btn.click(
                on_push,
                inputs=[push_password, commit_message],
                outputs=[push_result],
            )

        return ui
