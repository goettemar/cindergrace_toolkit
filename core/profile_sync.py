"""Profile Sync Service - Load workflow profiles from remote sources."""

import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class RemoteProfile:
    """A remote profile reference."""

    id: str
    name: str
    description: str
    url: str
    version: str


class ProfileSyncService:
    """Service to sync workflow profiles from remote sources.

    Workflow:
    1. Load profile index from remote URL
    2. Cache profiles locally
    3. Allow runtime updates without restarting

    Remote URL structure:
    - profiles/index.json -> List of available profiles
    - profiles/svi_wan22.json -> Individual profile
    """

    CACHE_DIR = Path(__file__).parent.parent / "profiles" / ".cache"

    def __init__(self, base_url: str = ""):
        self.base_url = base_url.rstrip("/")
        self._index: list[RemoteProfile] = []
        self._cached_profiles: dict[str, dict[str, Any]] = {}

        # SSL context for HTTPS (secure by default, configurable)
        from core.ssl_utils import get_ssl_context

        self._ssl_ctx = get_ssl_context()

    def set_base_url(self, url: str) -> None:
        """Set the base URL for remote profiles."""
        self.base_url = url.rstrip("/")
        self._index = []  # Clear cached index

    def _fetch_json(self, url: str, timeout: int = 30) -> dict[str, Any] | None:
        """Fetch JSON from URL."""
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "CindergaceToolkit/1.0",
                    "Accept": "application/json",
                },
            )

            with urllib.request.urlopen(req, context=self._ssl_ctx, timeout=timeout) as response:
                content = response.read().decode("utf-8")
                return json.loads(content)

        except Exception as e:
            print(f"[ProfileSync] Error fetching {url}: {e}")
            return None

    def fetch_index(self) -> list[RemoteProfile]:
        """Fetch the profile index from remote server."""
        if not self.base_url:
            print("[ProfileSync] No base URL configured")
            return []

        index_url = f"{self.base_url}/index.json"
        data = self._fetch_json(index_url)

        if not data:
            return []

        self._index = []
        for item in data.get("profiles", []):
            self._index.append(
                RemoteProfile(
                    id=item.get("id", ""),
                    name=item.get("name", "Unknown"),
                    description=item.get("description", ""),
                    url=item.get("url", ""),
                    version=item.get("version", "1.0.0"),
                )
            )

        print(f"[ProfileSync] Loaded {len(self._index)} profiles from index")
        return self._index

    def get_available_profiles(self) -> list[RemoteProfile]:
        """Get list of available remote profiles."""
        if not self._index:
            self.fetch_index()
        return self._index

    def fetch_profile(self, profile_id: str) -> dict[str, Any] | None:
        """Fetch a specific profile by ID."""
        # Check cache first
        if profile_id in self._cached_profiles:
            return self._cached_profiles[profile_id]

        # Find profile in index
        profile_ref = None
        for p in self._index:
            if p.id == profile_id:
                profile_ref = p
                break

        if not profile_ref:
            print(f"[ProfileSync] Profile not found in index: {profile_id}")
            return None

        # Construct URL
        if profile_ref.url.startswith("http"):
            url = profile_ref.url
        else:
            url = f"{self.base_url}/{profile_ref.url}"

        data = self._fetch_json(url)
        if data:
            self._cached_profiles[profile_id] = data
            self._save_to_cache(profile_id, data)

        return data

    def _save_to_cache(self, profile_id: str, data: dict[str, Any]) -> None:
        """Save profile to local cache."""
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = self.CACHE_DIR / f"{profile_id}.json"

        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[ProfileSync] Error caching profile: {e}")

    def load_from_cache(self, profile_id: str) -> dict[str, Any] | None:
        """Load profile from local cache."""
        cache_file = self.CACHE_DIR / f"{profile_id}.json"

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[ProfileSync] Error loading cached profile: {e}")
            return None

    def clear_cache(self) -> None:
        """Clear all cached profiles."""
        if self.CACHE_DIR.exists():
            for f in self.CACHE_DIR.glob("*.json"):
                f.unlink()
        self._cached_profiles = {}

    def get_local_profiles(self) -> list[str]:
        """Get list of locally saved/cached profiles."""
        profiles_dir = Path(__file__).parent.parent / "profiles"
        profiles = []

        if profiles_dir.exists():
            for f in profiles_dir.glob("*.json"):
                if f.name != "index.json":
                    profiles.append(f.stem)

        return profiles
