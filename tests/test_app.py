"""End-to-end Streamlit interaction without making a paid API request."""

from streamlit.testing.v1 import AppTest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

import pharma_insight.insights as insights
import pharma_insight.qa as qa
from pharma_insight.setup import ROOT


def test_ai_button_shows_and_keeps_verified_explanation(monkeypatch):
    monkeypatch.setattr(insights, "configured_api_key", lambda path: "test-key")
    monkeypatch.setattr(
        insights, "cloud_llm_insight",
        lambda facts, key: (
            "- Review the lower revenue region's coverage before changing targets.",
            "OpenAI explanation via LangChain · test model",
        ),
    )
    app = AppTest.from_file(str(ROOT / "app.py")).run(timeout=40)
    assert not app.exception
    assert not app.button[0].disabled

    app.button[0].click().run(timeout=40)
    assert not app.exception
    assert any("lower revenue region" in item.value for item in app.markdown)

    app.run(timeout=40)
    assert not app.exception
    assert any("lower revenue region" in item.value for item in app.markdown)


def test_chat_question_shows_verified_sql_and_persists(monkeypatch):
    monkeypatch.setattr(insights, "configured_api_key", lambda path: "test-key")
    monkeypatch.setattr(qa, "chat_model", lambda key: FakeListChatModel(
        responses=["Review unit movement and territory mix before changing plans."]))
    app = AppTest.from_file(str(ROOT / "app.py")).run(timeout=40)
    assert not app.exception
    assert len(app.chat_input) == 1
    app.chat_input[0].set_value(
        "Which medicine performed poorly last month, and what should we do?").run(timeout=40)
    assert not app.exception
    assert any("Immunara" in item.value for item in app.markdown)
    assert any("Suggested checks" in item.value for item in app.markdown)
    app.run(timeout=40)
    assert not app.exception
    assert any("Suggested checks" in item.value for item in app.markdown)
