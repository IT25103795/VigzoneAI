import re
from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_normal_assistant_text_is_unboxed_but_special_outputs_keep_a_surface():
    css = _read("static/css/styles.css")
    js = _read("static/js/app.js")

    natural_layout = css.split("Natural assistant response layout", 1)[1]
    assert ".msg.assistant .bubble{" in natural_layout
    assert "background:transparent;" in natural_layout
    assert "box-shadow:none;" in natural_layout
    assert ".msg.assistant .bubble.has-special-output" in natural_layout
    assert "background:var(--bubble-assistant-bg);" in natural_layout

    assert "SPECIAL_ASSISTANT_OUTPUT_SELECTOR" in js
    assert "syncAssistantOutputPresentation" in js
    assert "'.gen-image-wrap'" in js
    assert "'.file-bundle'" in js
    assert "'pre'" in js
    assert "'object[type=\"application/pdf\"]'" in js


def test_streaming_is_paced_and_reader_scroll_is_not_forced():
    js = _read("static/js/app.js")

    assert "function createPacedAssistantRenderer" in js
    assert js.count("pacedReply.append(parsed.content)") == 3
    assert js.count("await pacedReply.finish()") == 3
    assert "function scrollLatestIfFollowing" in js
    assert "followLatestMessage = false" in js
    assert "main.addEventListener('touchmove'" in js
    assert "scrollLatestIfFollowing();" in js


def test_feedback_icons_match_the_transparent_message_actions():
    css = _read("static/css/styles.css")
    js = _read("static/js/app.js")

    assert "const ICON_THUMBS_UP" in js
    assert "const ICON_THUMBS_DOWN" in js
    assert "upBtn.innerHTML = ICON_THUMBS_UP;" in js
    assert "downBtn.innerHTML = ICON_THUMBS_DOWN;" in js
    assert "upBtn.textContent = '👍';" not in js
    assert "downBtn.textContent = '👎';" not in js
    assert "message-action-btn feedback-btn feedback-up" in js
    assert "message-action-btn feedback-btn feedback-down" in js
    assert ".msg.assistant .feedback-btn.done svg" in css
    assert "fill:currentColor;" in css


def test_message_context_menu_replaces_swipe_to_reply():
    css = _read("static/css/styles.css")
    js = _read("static/js/app.js")

    assert "const ICON_REPLY" in js
    assert 'data-message-action="reply"' in js
    assert 'data-message-action="copy"' in js
    assert "<span>Reply</span>" in js
    assert "<span>Copy message</span>" in js
    assert "setQuote(reply.role, reply.fullText, reply.index);" in js
    assert "chatInner.addEventListener('contextmenu'" in js
    assert "messageContextLongPressTimer = window.setTimeout" in js
    assert "messageContextTouchStart.opened = true;" in js
    assert "'.msg.user,.msg.assistant'" in js
    assert ".message-context-menu{" in css
    assert "touch-action:pan-y pinch-zoom;" in css

    assert "Drag-to-quote functionality" not in js
    assert "dragStartX" not in js
    assert "draggedMsg" not in js
    assert "translateX(${Math.min(dx, 80)}px)" not in js
    assert ".message-copy-menu" not in css
    assert ".msg-quote-btn" not in css


def test_chat_ui_asset_revision_is_consistent():
    index = _read("static/index.html")
    service_worker = _read("static/service-worker.js")

    assert index.count("doodle-themes-r1") == 2
    assert "const UI_ASSET_REVISION = 'doodle-themes-r1';" in service_worker
    assert "const VIGZONE_SW_VERSION = 'vigzone-v5.0.0-production-r11';" in service_worker
    assert "/static/icons/vigzone-doodles.svg?v=doodle-r1" in service_worker


def test_curated_doodle_themes_replace_custom_wallpapers_and_binary_toggle():
    index = _read("static/index.html")
    js = _read("static/js/app.js")
    css = _read("static/css/styles.css")
    doodles = _read("static/icons/vigzone-doodles.svg")

    themes = {"charcoal", "midnight", "forest", "plum", "ember", "paper"}
    assert index.count('data-chat-theme-option="') == len(themes)
    assert all(f'data-chat-theme-option="{theme}"' in index for theme in themes)
    assert "CHAT_THEMES = Object.freeze" in js
    assert "function applyChatTheme" in js
    assert "function selectChatTheme" in js
    assert "data-chat-theme" in index
    assert ".chat-theme-layer::after" in css
    assert "vigzone-doodles.svg?v=doodle-r1" in css
    assert "whatsapp" not in doodles.lower()

    assert "chatWallpaperInput" not in index
    assert "wallpaperBlurRange" not in index
    assert "wallpaperBrightnessRange" not in index
    assert "resetWallpaperBtn" not in index
    assert "chatWallpaperInput" not in js
    assert "setWallpaperCss" not in js
    assert "toggleTheme" not in js
    assert "themeToggleBtnSidebar" not in index
    assert "body.has-chat-wallpaper" not in css


def _contrast_ratio(foreground: str, background: str) -> float:
    def luminance(color: str) -> float:
        channels = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4 for channel in channels]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    light, dark = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def test_every_doodle_theme_keeps_chat_text_and_user_bubbles_readable():
    css = _read("static/css/styles.css")

    def variables(selector_pattern: str) -> dict[str, str]:
        match = re.search(selector_pattern + r"\s*\{(?P<body>.*?)\n\s*\}", css, re.S)
        assert match, selector_pattern
        return dict(re.findall(r"--([\w-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;", match.group("body")))

    dark = variables(r":root,\s*\[data-theme=\"dark\"\]")
    light = variables(r"\[data-theme=\"light\"\]")
    tones = {
        "charcoal": "dark",
        "midnight": "dark",
        "forest": "dark",
        "plum": "dark",
        "ember": "dark",
        "paper": "light",
    }

    for theme, tone in tones.items():
        palette = dict(dark if tone == "dark" else light)
        if theme != "charcoal":
            palette.update(variables(rf"\[data-chat-theme=\"{theme}\"\]"))
        assert _contrast_ratio(palette["text"], palette["chat-theme-base"]) >= 7.0, theme
        assert _contrast_ratio(palette["on-accent-muted"], palette["accent"]) >= 4.5, theme
        assert _contrast_ratio(palette["on-accent-muted"], palette["accent-hover"]) >= 4.5, theme
