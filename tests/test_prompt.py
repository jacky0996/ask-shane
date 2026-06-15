"""prompt 組裝與 SHOW_SOURCES 覆寫的單元測試(不呼叫 Gemini)。"""

import ask
import config


def test_build_user_message_contains_context_and_question():
    hits = [
        ("doc text 1", {"source": "profile.md", "heading": "h"}),
        ("doc text 2", {"source": "projects/x/README.md", "heading": "h2"}),
    ]
    msg = ask.build_user_message("他會 Python 嗎?", hits)
    assert "<context>" in msg and "</context>" in msg
    assert "他會 Python 嗎?" in msg
    assert "profile.md" in msg
    assert "doc text 1" in msg


def test_dev_mode_keeps_sources(monkeypatch):
    monkeypatch.setattr(config, "SHOW_SOURCES", True)
    assert ask._NO_SOURCE_OVERRIDE not in ask.load_system_prompt()


def test_prod_mode_appends_no_source_override(monkeypatch):
    monkeypatch.setattr(config, "SHOW_SOURCES", False)
    assert ask._NO_SOURCE_OVERRIDE in ask.load_system_prompt()
