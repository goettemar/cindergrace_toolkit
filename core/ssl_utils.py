"""SSL utilities with configurable verification."""

import json
import ssl
from pathlib import Path
from typing import Optional


def get_ssl_context(config_dir: Optional[Path] = None) -> ssl.SSLContext:
    """Get SSL context based on configuration.

    SSL verification is ENABLED by default. To disable (INSECURE):
    Add to config.json or .config/config.json:
    {
        "security": {
            "disable_ssl_verify": true
        }
    }

    Args:
        config_dir: Optional path to config directory. If None, uses project root.

    Returns:
        Configured SSL context
    """
    if config_dir is None:
        config_dir = Path(__file__).parent.parent

    # Check for disable_ssl_verify in config
    disable_ssl = False

    for config_path in [
        config_dir / ".config" / "config.json",
        config_dir / "config" / "config.json",
    ]:
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    disable_ssl = config.get("security", {}).get("disable_ssl_verify", False)
                    break
            except Exception:
                pass

    if disable_ssl:
        # INSECURE: Disable SSL verification
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    # Default: Secure SSL verification
    return ssl.create_default_context()
