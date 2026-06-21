import json
import os
import shutil
import tempfile
from self_learning import (
    _ensure_kb,
    _load_kb,
    add_interaction,
    find_similar,
    get_context_for_prompt,
    is_degenerate_text,
    prune_kb,
    sanitize_assistant_for_memory,
    trim_degeneration_tail,
    KB_PATH,
    KB_DIR,
)


def run_with_temp_kb(fn):
    """Run a test function against an isolated KB file."""
    fd, tmp_path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.makedirs(KB_DIR, exist_ok=True)
    backup = KB_PATH + ".bak" if os.path.exists(KB_PATH) else None
    if backup:
        shutil.copy2(KB_PATH, backup)
    try:
        import self_learning as sl

        old_path = sl.KB_PATH
        sl.KB_PATH = tmp_path
        _ensure_kb()
        try:
            fn()
        finally:
            sl.KB_PATH = old_path
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        if backup:
            shutil.move(backup, KB_PATH)


def test_degenerate_detection():
    loop = (
        "## Step 1: \nTo verify; \nThat's \n\n" * 8
        + "_(Stopped early — I started repeating myself. Mind rephrasing the question?)_"
    )
    assert is_degenerate_text(loop)

    echo = (
        "Good answer first. By the way; I am still learning; I can improve my responses; "
        "I'm here; I'm here; I'm Vigzone AI; I'm here; I'm here;"
    )
    assert is_degenerate_text(echo)

    clean = "Claude is a conversational AI model developed by Anthropic."
    assert not is_degenerate_text(clean)

    chatgpt = (
        "I'm Vigzone AI! 😊 What's your connection to ChatGPT? 💡 \n\n"
        "By the way; I provide helpful context from past examples; I'm here; I'm here"
    )
    trimmed = trim_degeneration_tail(chatgpt)
    assert "By the way;" not in trimmed
    assert trimmed.endswith("💡")

    natural_aside = (
        "I passed the test!\n\nBy the way, I think I see what you did there with the pause/play test 😉."
    )
    assert trim_degeneration_tail(natural_aside) == natural_aside


def _test_sanitize_and_prune():
    bad = (
        "Nice reply about Claude. By the way; I am still learning; "
        + "I'm here; I'm here; I'm Vigzone AI; " * 5
    )
    safe = sanitize_assistant_for_memory(bad)
    assert safe.startswith("Nice reply about Claude.")
    assert "I'm here; I'm here" not in safe
    assert not is_degenerate_text(safe)

    add_interaction("Who is Claude?", bad)
    kb = _load_kb()
    assert len(kb) == 1
    assert "I'm here; I'm here" not in kb[0]["assistant"]

    add_interaction("Loop only", bad)
    prune_kb()
    kb = _load_kb()
    assert all("I'm here; I'm here" not in e["assistant"] for e in kb)


def _demo_similarity_search():
    add_interaction(
        "How do I center a div in CSS?",
        "Use margin: 0 auto; on a block with width or flexbox centering.",
    )
    add_interaction(
        "What's the best way to learn Python?",
        "Practice projects, read docs, use exercises.",
    )
    add_interaction(
        "How to center text vertically?",
        "Use line-height or flexbox align-items:center.",
    )

    kb = _load_kb()
    print(f"KB entries: {len(kb)}")

    q = "How can I center something horizontally in CSS?"
    hits = find_similar(q, top_k=2)
    print("Similar hits:")
    print(json.dumps(hits, indent=2, ensure_ascii=False))

    ctx = get_context_for_prompt(q)
    print("Context block:\n", ctx)


def main():
    test_degenerate_detection()
    run_with_temp_kb(_test_sanitize_and_prune)
    run_with_temp_kb(_demo_similarity_search)
    print("All self-learning checks passed.")


if __name__ == "__main__":
    main()
