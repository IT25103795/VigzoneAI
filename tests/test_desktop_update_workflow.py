from pathlib import Path

import desktop_updates


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _release(version: str, *, prerelease: bool = False, draft: bool = False, assets=None):
    return {
        "tag_name": f"v{version}",
        "name": f"Vigzone Desktop {version}",
        "body": "A focused release note.",
        "html_url": f"https://github.com/IT25103795/VigzoneAI/releases/tag/v{version}",
        "published_at": "2026-08-14T00:00:00Z",
        "prerelease": prerelease,
        "draft": draft,
        "assets": assets or [],
    }


def test_stable_channel_ignores_drafts_and_prereleases():
    releases = [
        _release("2.0.0", draft=True),
        _release("1.2.0-beta.1", prerelease=True),
        _release("1.1.0"),
    ]

    assert desktop_updates._select_release(releases, "stable")["tag_name"] == "v1.1.0"
    assert desktop_updates._select_release(releases, "beta")["tag_name"] == "v1.2.0-beta.1"


def test_release_payload_prefers_the_x64_setup_executable():
    release = _release(
        "1.0.1",
        assets=[
            {"name": "Vigzone-arm64.exe", "browser_download_url": "https://github.com/a/arm64.exe", "size": 1},
            {"name": "Vigzone-AI-win32-x64-Setup.exe", "browser_download_url": "https://github.com/a/setup.exe", "size": 42},
            {"name": "release.zip", "browser_download_url": "https://github.com/a/release.zip", "size": 2},
        ],
    )

    payload = desktop_updates._public_release_payload("IT25103795/VigzoneAI", "stable", release)

    assert payload["release"]["version"] == "1.0.1"
    assert payload["release"]["download_name"] == "Vigzone-AI-win32-x64-Setup.exe"
    assert payload["release"]["download_url"] == "https://github.com/a/setup.exe"
    assert payload["release"]["download_size"] == 42


def test_release_endpoint_returns_only_the_sanitized_cached_result(client, monkeypatch):
    expected = desktop_updates._public_release_payload(
        "IT25103795/VigzoneAI",
        "stable",
        _release("1.0.1"),
    )

    async def fake_latest():
        return expected

    monkeypatch.setattr(desktop_updates, "latest_desktop_release", fake_latest)
    response = client.get("/api/desktop/releases/latest")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == expected
    assert "token" not in response.text.lower()


def test_update_ui_uses_real_release_data_and_manual_trusted_downloads():
    index = _read("static/index.html")
    app_js = _read("static/js/app.js")
    service_worker = _read("static/service-worker.js")
    main = _read("desktop/main.cjs")

    assert 'id="quickUpdateBtn"' in index
    assert index.index('id="quickLauncherToggle"') < index.index('id="quickUpdateBtn"')
    assert "/api/desktop/releases/latest" in app_js
    assert "compareDesktopVersions" in app_js
    assert "getAppVersion?.()" in app_js
    assert "notifyUpdate?.(" in app_js
    assert "VigzoneDesktopUpdates" in app_js
    assert "githubusercontent.com" in app_js
    assert "isMobileDevice" in app_js
    assert "canDownloadWindows" in app_js
    assert "state.isDesktop ? state.hasUpdate : state.canDownloadWindows" in app_js
    assert "desktop-update-card ${cardStateClass}" in app_js
    assert "No download needed" in app_js
    assert "Web platform · Features update automatically" in app_js
    assert "Render/web build:" not in app_js
    assert "/api/desktop/releases/latest" in service_worker
    assert "desktop:notify-update" in main
    assert "trustedMainSender" in main
    assert "autoUpdater" not in main
    assert "quitAndInstall" not in app_js
