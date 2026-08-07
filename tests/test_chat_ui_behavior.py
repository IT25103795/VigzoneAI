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


def test_chat_ui_asset_revision_is_consistent():
    index = _read("static/index.html")
    service_worker = _read("static/service-worker.js")

    assert index.count("feedback-actions-r1") == 2
    assert "const UI_ASSET_REVISION = 'feedback-actions-r1';" in service_worker
    assert "const VIGZONE_SW_VERSION = 'vigzone-v5.0.0-production-r9';" in service_worker
