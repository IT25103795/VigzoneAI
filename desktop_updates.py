"""Server-side GitHub Release discovery for the Vigzone desktop client.

The browser never receives a GitHub token. Public releases work without one;
an optional server-only token raises GitHub's API rate limit for the Render
service. Release responses are cached per process to avoid one GitHub request
per connected user.
"""

from __future__ import annotations

import asyncio
import os
import re
import time
from datetime import datetime, timezone
from typing import Any

import httpx


DEFAULT_RELEASE_REPOSITORY = "IT25103795/VigzoneAI"
_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SEMVER_RE = re.compile(r"(?i)(\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?)")
_CACHE_LOCK = asyncio.Lock()
_CACHE_VALUE: dict[str, Any] | None = None
_CACHE_EXPIRES_AT = 0.0


class DesktopReleaseLookupError(RuntimeError):
    """A safe, user-facing release lookup failure."""


def release_repository() -> str:
    value = os.getenv("VIGZONE_DESKTOP_RELEASE_REPO", DEFAULT_RELEASE_REPOSITORY).strip()
    if not _REPOSITORY_RE.fullmatch(value):
        raise DesktopReleaseLookupError("The desktop release repository is not configured correctly.")
    return value


def release_channel() -> str:
    value = os.getenv("VIGZONE_UPDATE_CHANNEL", "stable").strip().lower()
    return "beta" if value in {"beta", "prerelease", "preview", "all"} else "stable"


def _version_from_release(release: dict[str, Any]) -> str:
    source = str(release.get("tag_name") or release.get("name") or "")
    match = _SEMVER_RE.search(source)
    return match.group(1) if match else ""


def _select_release(releases: list[dict[str, Any]], channel: str) -> dict[str, Any] | None:
    eligible = [item for item in releases if isinstance(item, dict) and not item.get("draft")]
    if channel == "stable":
        eligible = [item for item in eligible if not item.get("prerelease")]
    return next((item for item in eligible if _version_from_release(item)), None)


def _select_windows_installer(release: dict[str, Any]) -> dict[str, Any] | None:
    assets = [item for item in release.get("assets", []) if isinstance(item, dict)]
    executables = [
        item for item in assets
        if str(item.get("name") or "").lower().endswith(".exe")
        and str(item.get("browser_download_url") or "").startswith("https://")
    ]

    def score(asset: dict[str, Any]) -> int:
        name = str(asset.get("name") or "").lower()
        value = 0
        if "setup" in name or "installer" in name:
            value += 100
        if "win32" in name:
            value += 30
        if "x64" in name:
            value += 20
        if "arm64" in name or "ia32" in name:
            value -= 100
        return value

    return max(executables, key=score, default=None)


def _public_release_payload(repository: str, channel: str, release: dict[str, Any] | None) -> dict[str, Any]:
    checked_at = datetime.now(timezone.utc).isoformat()
    if not release:
        return {
            "ok": True,
            "repository": repository,
            "channel": channel,
            "checked_at": checked_at,
            "release": None,
        }

    installer = _select_windows_installer(release)
    release_url = str(release.get("html_url") or "")
    download_url = str(installer.get("browser_download_url") or "") if installer else ""
    return {
        "ok": True,
        "repository": repository,
        "channel": channel,
        "checked_at": checked_at,
        "release": {
            "version": _version_from_release(release),
            "tag": str(release.get("tag_name") or ""),
            "name": str(release.get("name") or release.get("tag_name") or "Vigzone desktop update")[:180],
            "notes": str(release.get("body") or "")[:8000],
            "published_at": release.get("published_at"),
            "prerelease": bool(release.get("prerelease")),
            "release_url": release_url if release_url.startswith("https://github.com/") else "",
            "download_url": download_url,
            "download_name": str(installer.get("name") or "")[:240] if installer else "",
            "download_size": max(0, int(installer.get("size") or 0)) if installer else 0,
        },
    }


async def latest_desktop_release() -> dict[str, Any]:
    """Return the latest configured desktop release, using a stale-safe cache."""
    global _CACHE_EXPIRES_AT, _CACHE_VALUE

    now = time.monotonic()
    if _CACHE_VALUE is not None and now < _CACHE_EXPIRES_AT:
        return dict(_CACHE_VALUE)

    async with _CACHE_LOCK:
        now = time.monotonic()
        if _CACHE_VALUE is not None and now < _CACHE_EXPIRES_AT:
            return dict(_CACHE_VALUE)

        repository = release_repository()
        channel = release_channel()
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "VigzoneAI-Desktop-Release-Checker",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        token = os.getenv("GITHUB_RELEASES_TOKEN", "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        url = f"https://api.github.com/repos/{repository}/releases?per_page=20"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(8.0), follow_redirects=False) as client:
                response = await client.get(url, headers=headers)
            response.raise_for_status()
            releases = response.json()
            if not isinstance(releases, list):
                raise DesktopReleaseLookupError("GitHub returned an invalid desktop release response.")
            value = _public_release_payload(repository, channel, _select_release(releases, channel))
            ttl = max(60, min(int(os.getenv("VIGZONE_UPDATE_CACHE_SECONDS", "300")), 3600))
            _CACHE_VALUE = value
            _CACHE_EXPIRES_AT = time.monotonic() + ttl
            return dict(value)
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            if _CACHE_VALUE is not None:
                stale = dict(_CACHE_VALUE)
                stale["stale"] = True
                return stale
            raise DesktopReleaseLookupError(
                "Vigzone could not reach the desktop release service. Please try again shortly."
            ) from exc


def _reset_release_cache_for_tests() -> None:
    global _CACHE_EXPIRES_AT, _CACHE_VALUE
    _CACHE_VALUE = None
    _CACHE_EXPIRES_AT = 0.0
