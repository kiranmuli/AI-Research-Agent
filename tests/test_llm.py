import pytest

from app.llm.factory import build_provider


def test_factory_builds_ollama():
    p = build_provider("ollama")
    assert p.provider_name == "ollama"


def test_factory_builds_anthropic():
    p = build_provider("anthropic")
    assert p.provider_name == "anthropic"


def test_factory_rejects_unknown():
    with pytest.raises(ValueError):
        build_provider("does-not-exist")


def test_anthropic_unavailable_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    import app.settings as settings_mod

    settings_mod.get_settings.cache_clear()
    from app.llm.anthropic_provider import AnthropicProvider

    ok, msg = AnthropicProvider(api_key=None).is_available()
    assert not ok and "ANTHROPIC_API_KEY" in msg
